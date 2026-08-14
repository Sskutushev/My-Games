from __future__ import annotations

import pytest

from dl_toolkit.binio import BinaryFormatError, Writer
from dl_toolkit.codecs import (
    CodeFileCodec,
    FixedTableCodec,
    LootListCodec,
    MonSoundCodec,
    ScriptFile,
    ScriptLine,
    StringTable,
    StringTableCodec,
)

# ------------------------------------------------------------------ strtab


def build_strtab(entries: list[tuple[int, str]], *, intern: bool = False) -> bytes:
    return StringTableCodec(intern=intern).encode(StringTable(entries))


def test_strtab_roundtrip():
    codec = StringTableCodec()
    data = build_strtab([(1, "меч"), (2, "щит"), (5, "меч")])
    model = codec.decode(data)
    assert model.entries == [(1, "меч"), (2, "щит"), (5, "меч")]
    assert codec.encode(model) == data


def test_strtab_does_not_intern_by_default():
    plain = build_strtab([(1, "aaaa"), (2, "aaaa")])
    interned = build_strtab([(1, "aaaa"), (2, "aaaa")], intern=True)
    assert len(plain) > len(interned)
    assert StringTableCodec(intern=True).roundtrip_ok(interned)


def test_strtab_accessors():
    model = StringTable([(1, "меч"), (2, "щит")])
    assert model.as_dict() == {1: "меч", 2: "щит"}
    assert model.get(1) == "меч"
    assert model.get(99, "нет") == "нет"
    assert len(model) == 2

    model.set(1, "клинок")
    assert model.get(1) == "клинок"
    model.set(7, "посох")
    assert model.entries[-1] == (7, "посох")
    assert model.free_ids(1, 4) == [3, 4]


def test_strtab_rejects_impossible_count():
    with pytest.raises(BinaryFormatError, match="не помещается"):
        StringTableCodec().decode(Writer().u32(9999).data())


# ------------------------------------------------------------------ fixedtab


def build_fixed(records: list[tuple[str, str, bytes]], record_size: int, name: int, kind: int):
    writer = Writer().u32(len(records)).pad_to(record_size)
    for record_name, record_kind, tail in records:
        writer.fixed_str(record_name, name)
        if kind:
            writer.fixed_str(record_kind, kind)
        writer.raw(tail)
    return writer.data()


def test_fixedtab_roundtrip_with_kind():
    data = build_fixed([("Меч", "Клинок", b"\x01\x00\x02\x00")], 20, 8, 8)
    codec = FixedTableCodec(20, 8, 8)
    model = codec.decode(data)
    assert len(model) == 1
    assert model.by_index(1).name == "Меч"
    assert model.by_index(1).kind == "Клинок"
    assert model.declared_count == 1
    assert codec.encode(model) == data


def test_fixedtab_preserves_garbage_after_terminator():
    """После NUL в поле имени в оригиналах остаётся мусор; он обязан пережить round-trip."""
    dirty = b"AB\x00XY" + b"\x00" * 1 + b"\x09\x00"
    codec = FixedTableCodec(8, 6, 0)
    data = Writer().u32(1).pad_to(8).raw(dirty).data()
    model = codec.decode(data)
    assert model.by_index(1).name == "AB"
    assert codec.encode(model) == data


def test_fixedtab_numeric_access():
    data = build_fixed([("A", "", b"\x05\x00\x07\x00")], 12, 8, 0)
    model = FixedTableCodec(12, 8, 0).decode(data)
    record = model.by_index(1)
    assert record.u16(8) == 5
    assert record.u16(10) == 7
    record.set_u16(8, 99)
    assert record.u16(8) == 99
    assert model.u16_column(10) == [(1, 7)]


def test_fixedtab_numeric_access_bounds():
    model = FixedTableCodec(12, 8, 0).decode(build_fixed([("A", "", b"\x00" * 4)], 12, 8, 0))
    record = model.by_index(1)
    with pytest.raises(BinaryFormatError, match="вне числовой части"):
        record.u16(0)
    with pytest.raises(BinaryFormatError, match="вне числовой части"):
        record.set_u16(200, 1)


def test_fixedtab_free_slots_and_editing():
    data = build_fixed([("Меч", "", b"\x00\x00"), ("", "", b"\x00\x00")], 10, 8, 0)
    model = FixedTableCodec(10, 8, 0).decode(data)
    assert model.free_slots() == [2]
    model.by_index(2).name = "Новый"
    assert model.free_slots() == []
    model.declared_count = 5
    assert model.declared_count == 5


def test_fixedtab_name_overflow_rejected():
    model = FixedTableCodec(10, 4, 0).decode(build_fixed([("ab", "", b"\x00" * 6)], 10, 4, 0))
    with pytest.raises(BinaryFormatError, match="не помещается"):
        model.by_index(1).name = "abcdefgh"


def test_fixedtab_kind_setter_requires_field():
    model = FixedTableCodec(10, 4, 0).decode(build_fixed([("ab", "", b"\x00" * 6)], 10, 4, 0))
    with pytest.raises(BinaryFormatError, match="нет поля вида"):
        model.by_index(1).kind = "x"


def test_fixedtab_rejects_bad_sizes():
    with pytest.raises(ValueError, match="положительным"):
        FixedTableCodec(0, 1)
    with pytest.raises(ValueError, match="не помещаются"):
        FixedTableCodec(4, 4, 4)
    with pytest.raises(BinaryFormatError, match="не кратен"):
        FixedTableCodec(8, 4).decode(b"\x00" * 9)
    with pytest.raises(BinaryFormatError, match="пуста"):
        FixedTableCodec(8, 4).decode(b"")


def test_fixedtab_missing_record_raises():
    model = FixedTableCodec(8, 4).decode(build_fixed([("a", "", b"\x00" * 4)], 8, 4, 0))
    with pytest.raises(KeyError, match="нет в таблице"):
        model.by_index(42)


def test_fixedtab_encode_validates_shapes():
    codec = FixedTableCodec(8, 4)
    model = codec.decode(build_fixed([("a", "", b"\x00" * 4)], 8, 4, 0))
    model.marker = b"\x00"
    with pytest.raises(BinaryFormatError, match="маркера"):
        codec.encode(model)

    model = codec.decode(build_fixed([("a", "", b"\x00" * 4)], 8, 4, 0))
    model.records[0].tail = b"\x00"
    with pytest.raises(BinaryFormatError, match="хвост записи"):
        codec.encode(model)

    model = codec.decode(build_fixed([("a", "", b"\x00" * 4)], 8, 4, 0))
    model.records[0].name_raw = b"\x00"
    with pytest.raises(BinaryFormatError, match="поле имени"):
        codec.encode(model)


# ------------------------------------------------------------------ codefile


def build_script(lines: list[tuple[int, str]]) -> bytes:
    writer = Writer()
    for tag, text in lines:
        block = text.encode("cp1251") + b"\x00"
        writer.u32(tag).u32(len(block)).raw(block)
    return writer.data()


def test_codefile_roundtrip():
    data = build_script(
        [(0, "\tif flag(%FLAG_INIT) = (1)"), (11, "\t\tgoto $GREETING."), (14, "\tendif")]
    )
    codec = CodeFileCodec()
    model = codec.decode(data)
    assert len(model) == 3
    assert model.lines[1].tag == 11
    assert codec.encode(model) == data


def test_codefile_keeps_trailing_bytes():
    writer = Writer()
    block = b"\ttext\x00\xde\xad"
    writer.u32(3).u32(len(block)).raw(block)
    data = writer.data()
    codec = CodeFileCodec()
    assert codec.roundtrip_ok(data)
    assert codec.decode(data).lines[0].trailing == b"\xde\xad"


def test_codefile_helpers():
    model = CodeFileCodec().decode(
        build_script([(0, "\t$GREETING."), (1, '\tmsg "привет".'), (2, "\tgoto $EXIT.")])
    )
    assert model.labels() == {"$GREETING": 0}
    assert model.lines[0].is_label
    assert model.lines[1].keyword == "msg"
    assert model.lines[0].keyword == ""
    assert model.lines[2].statement == "goto $EXIT"
    assert model.find("msg") == [1]
    assert len(model.statements()) == 3


def test_codefile_replace_text_keeps_tag():
    codec = CodeFileCodec()
    model = codec.decode(build_script([(7, '\tmsg "старое".')]))
    model.replace_text(0, '\tmsg "новое".')
    rebuilt = codec.decode(codec.encode(model))
    assert rebuilt.lines[0].tag == 7
    assert "новое" in rebuilt.lines[0].text
    with pytest.raises(IndexError):
        model.replace_text(99, "x")


def test_codefile_rejects_corrupt_input():
    codec = CodeFileCodec()
    with pytest.raises(BinaryFormatError, match="выходит за файл"):
        codec.decode(Writer().u32(0).u32(999).data())
    with pytest.raises(BinaryFormatError, match="без NUL"):
        codec.decode(Writer().u32(0).u32(2).raw(b"ab").data())
    with pytest.raises(BinaryFormatError, match="не разобран"):
        codec.decode(build_script([(0, "a")]) + b"\x01\x02\x03")


def test_codefile_empty_input():
    assert len(CodeFileCodec().decode(b"")) == 0
    assert CodeFileCodec().encode(ScriptFile([ScriptLine(1, "x")])).startswith(b"\x01\x00\x00\x00")


# ------------------------------------------------------------------ trlist


def build_loot(entries: list[tuple[str, list[int]]]) -> bytes:
    writer = Writer().u32(len(entries)).pad_to(60)
    for name, ids in entries:
        writer.fixed_str(name, 24).u16_array((ids + [0] * 18)[:18])
    return writer.data()


def test_trlist_roundtrip_and_stats():
    data = build_loot([("Common L1 Weapon", [10, 20, 30]), ("", [])])
    codec = LootListCodec()
    model = codec.decode(data)
    assert codec.encode(model) == data
    first = model.by_name("Common L1 Weapon")
    assert first.item_ids() == [10, 20, 30]
    assert first.used == 3
    assert first.free == 15
    assert model.empty_lists() == [2]
    assert model.free_capacity() == 15 + 18


def test_trlist_add_and_rename():
    model = LootListCodec().decode(build_loot([("Список", [1])]))
    entry = model.by_index(1)
    entry.add(42)
    assert entry.item_ids() == [1, 42]
    entry.name = "Новый список"
    assert entry.name == "Новый список"
    with pytest.raises(BinaryFormatError, match="длиннее"):
        entry.name = "x" * 30


def test_trlist_add_to_full_list_raises():
    model = LootListCodec().decode(build_loot([("Полный", list(range(1, 19)))]))
    with pytest.raises(BinaryFormatError, match="заполнен"):
        model.by_index(1).add(99)


def test_trlist_lookup_errors():
    model = LootListCodec().decode(build_loot([("A", [1])]))
    with pytest.raises(KeyError):
        model.by_name("нет такого")
    with pytest.raises(KeyError):
        model.by_index(77)


def test_trlist_rejects_bad_sizes():
    codec = LootListCodec()
    with pytest.raises(BinaryFormatError, match="не кратен"):
        codec.decode(b"\x00" * 61)
    model = codec.decode(build_loot([("A", [1])]))
    model.lists[0].entries = [1]
    with pytest.raises(BinaryFormatError, match="слотов вместо"):
        codec.encode(model)


# ------------------------------------------------------------------ monsound

SOUND_TEXT = (
    "***********\r\n"
    "742             * MAXIMUM # OF SOUND RECORDS\r\n"
    "***********\r\n"
    '0,"",11025,\t* SFX_0\r\n'
    '11,"spell_fireball.wav",22050,R,\t* DLORDS FIREBALL\r\n'
    '12,"dak_plasma.wav",11025,\r\n'
    "не строка записи\r\n"
    '-1,""\t* END OF SOUNDS\r\n'
)


def test_monsound_roundtrip_preserves_comments():
    data = SOUND_TEXT.encode("cp1251")
    codec = MonSoundCodec()
    assert codec.roundtrip_ok(data)
    model = codec.decode(data)
    assert model.max_records == 742
    assert [e.sfx_id for e in model.entries] == [0, 11, 12, -1]
    fireball = model.by_id(11)
    assert fireball.wav == "spell_fireball.wav"
    assert fireball.sample_rate == 22050
    assert fireball.resident is True
    assert fireball.comment == "DLORDS FIREBALL"
    assert model.by_id(12).resident is False


def test_monsound_free_ids_and_edit():
    codec = MonSoundCodec()
    model = codec.decode(SOUND_TEXT.encode("cp1251"))
    free = model.free_ids()
    assert 0 not in free
    assert 11 not in free
    assert 13 in free

    model.set_wav(11, "new.wav")
    rebuilt = codec.decode(codec.encode(model))
    assert rebuilt.by_id(11).wav == "new.wav"
    assert rebuilt.by_id(11).comment == "DLORDS FIREBALL"

    with pytest.raises(KeyError, match="нет в реестре"):
        model.by_id(9999)


def test_monsound_handles_lf_and_no_trailing_newline():
    codec = MonSoundCodec()
    data = '5,"a.wav",11025,'.encode("cp1251")
    model = codec.decode(data)
    assert model.line_ending == "\n"
    assert model.trailing_newline is False
    assert model.max_records == 0
    assert codec.encode(model) == data
