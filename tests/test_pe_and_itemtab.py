from __future__ import annotations

import struct

import pytest

from dl_toolkit.binio import BinaryFormatError
from dl_toolkit.game import GameRoot
from dl_toolkit.itemtab import (
    ITEM_ARRAY_BASE,
    ITEM_COUNT,
    ITEM_STRIDE,
    MAKEITEMS_VA,
    FieldWrite,
    ItemTable,
    extract,
)
from dl_toolkit.pe import PeImage

IMAGE_BASE = 0x400000


def build_pe(sections: list[tuple[str, int, int, bytes]]) -> bytes:
    """Собрать минимальный корректный PE для тестов кодека.

    sections: (имя, virtual_address, virtual_size, сырые байты)
    """
    header_size = 0x400
    out = bytearray(header_size)
    out[0:2] = b"MZ"
    pe_offset = 0x80
    struct.pack_into("<I", out, 0x3C, pe_offset)
    out[pe_offset : pe_offset + 4] = b"PE\0\0"
    coff = pe_offset + 4
    struct.pack_into("<H", out, coff + 2, len(sections))
    optional_size = 0xE0
    struct.pack_into("<H", out, coff + 16, optional_size)
    optional = coff + 20
    struct.pack_into("<I", out, optional + 28, IMAGE_BASE)

    table = optional + optional_size
    raw_pointer = header_size
    body = bytearray()
    for index, (name, virtual_address, virtual_size, payload) in enumerate(sections):
        entry = table + index * 40
        out[entry : entry + 8] = name.encode().ljust(8, b"\0")
        struct.pack_into(
            "<IIII", out, entry + 8, virtual_size, virtual_address, len(payload), raw_pointer
        )
        raw_pointer += len(payload)
        body += payload
    return bytes(out) + bytes(body)


@pytest.fixture
def tiny_image() -> PeImage:
    text = b"\x90" * 0x100
    rdata = b"HELLO\x00" + b"\xff\xfe" + b"\x00" * 8
    return PeImage.parse(
        build_pe(
            [
                (".text", 0x1000, 0x100, text),
                (".rdata", 0x2000, 0x200, rdata),  # virtual_size > raw: хвост не в файле
            ]
        )
    )


# ------------------------------------------------------------------ pe


def test_parse_rejects_non_pe():
    with pytest.raises(BinaryFormatError, match="не MZ"):
        PeImage.parse(b"XX" + b"\x00" * 100)
    broken = bytearray(build_pe([(".text", 0x1000, 0x10, b"\x90" * 16)]))
    broken[0x80:0x84] = b"XXXX"
    with pytest.raises(BinaryFormatError, match="сигнатура PE"):
        PeImage.parse(bytes(broken))


def test_address_translation_roundtrip(tiny_image: PeImage):
    virtual = IMAGE_BASE + 0x1000
    offset = tiny_image.to_offset(virtual)
    assert offset is not None
    assert tiny_image.to_virtual(offset) == virtual


def test_address_translation_out_of_range(tiny_image: PeImage):
    assert tiny_image.to_offset(IMAGE_BASE + 0x99999) is None
    assert tiny_image.to_virtual(10**9) is None


def test_offset_beyond_raw_data_is_none(tiny_image: PeImage):
    """Виртуальный размер секции больше сырого: хвост не читается."""
    assert tiny_image.to_offset(IMAGE_BASE + 0x2000 + 0x1F0) is None


def test_read_cstring(tiny_image: PeImage):
    assert tiny_image.read_cstring(IMAGE_BASE + 0x2000) == "HELLO"
    assert tiny_image.read_cstring(IMAGE_BASE + 0x2006) is None  # непечатаемые байты
    assert tiny_image.read_cstring(10**9) is None


def test_read_cstring_rejects_too_short(tiny_image: PeImage):
    assert tiny_image.read_cstring(IMAGE_BASE + 0x2005) is None


# ------------------------------------------------------------------ itemtab


def test_layout_constants_are_consistent():
    assert ITEM_COUNT * ITEM_STRIDE == 193392
    assert ITEM_STRIDE == 204


def test_item_table_grouping():
    table = ItemTable(
        [
            FieldWrite(ITEM_ARRAY_BASE + 4, 0, 4, 2, 7, 0x1000),
            FieldWrite(ITEM_ARRAY_BASE + 0, 0, 0, 4, None, 0x1005, source_string="PUNCH"),
            FieldWrite(ITEM_ARRAY_BASE + ITEM_STRIDE, 1, 0, 4, 3, 0x100A),
        ]
    )
    assert table.indices() == [0, 1]
    assert [w.field_offset for w in table.by_item(0)] == [0, 4]
    assert table.field_usage() == {0: 2, 4: 1}
    assert table.strings_for(0) == ["PUNCH"]


def test_extract_on_synthetic_makeitems():
    """Синтетический MakeITEMS: две записи в массив предметов и строка из .rdata."""
    pytest.importorskip("capstone")

    name_va = IMAGE_BASE + 0x2000
    code = bytearray()
    # mov dword ptr [ITEM_ARRAY_BASE], 0x2A
    code += b"\xc7\x05" + struct.pack("<I", ITEM_ARRAY_BASE) + struct.pack("<I", 0x2A)
    # mov eax, dword ptr [name_va]   — загрузка строки
    code += b"\xa1" + struct.pack("<I", name_va)
    # mov dword ptr [ITEM_ARRAY_BASE + STRIDE + 8], eax
    code += b"\xa3" + struct.pack("<I", ITEM_ARRAY_BASE + ITEM_STRIDE + 8)
    code += b"\xc3"  # ret

    text_rva = MAKEITEMS_VA - IMAGE_BASE
    image = PeImage.parse(
        build_pe(
            [
                (".text", text_rva, len(code) + 16, bytes(code)),
                (".rdata", 0x2000, 0x20, b"PUNCH\x00" + b"\x00" * 10),
            ]
        )
    )
    table = extract(image)
    assert table.indices() == [0, 1]

    first = table.by_item(0)[0]
    assert (first.field_offset, first.width, first.value) == (0, 4, 0x2A)

    second = table.by_item(1)[0]
    assert second.field_offset == 8
    assert second.source_string == "PUNCH"


def test_extract_rejects_image_without_makeitems():
    image = PeImage.parse(build_pe([(".text", 0x1000, 0x10, b"\xc3" * 16)]))
    with pytest.raises(ValueError, match="вне образа"):
        extract(image)


def test_extract_respects_instruction_limit():
    pytest.importorskip("capstone")
    text_rva = MAKEITEMS_VA - IMAGE_BASE
    code = b"\x90" * 64  # ни одного ret: остановит лимит
    image = PeImage.parse(build_pe([(".text", text_rva, len(code), code)]))
    assert extract(image, max_instructions=5).writes == []


@pytest.mark.gamedata
def test_real_exe_contains_item_table(real_game: GameRoot):
    """Ключевое открытие: таблица предметов вкомпилирована в dlords.exe."""
    pytest.importorskip("capstone")
    image = PeImage.parse(real_game.read("dlords.exe"))
    table = extract(image)

    indices = table.indices()
    assert min(indices) == 0
    assert max(indices) == ITEM_COUNT - 1
    assert len(table.writes) > 10_000

    # iname.dat объявляет ровно столько же предметов
    from dl_toolkit.codecs import StringTableCodec

    names = StringTableCodec().decode(real_game.read("iname.dat"))
    assert len(names) == ITEM_COUNT

    # соответствие индекса и id: iname_id = index + 1
    lookup = names.as_dict()
    assert lookup[1] == "PUNCH"
    assert lookup[4] == "CHAIN BOOTS"
    assert "CHAIN BOOTS" in " ".join(table.strings_for(3))


@pytest.mark.gamedata
def test_real_exe_has_no_d6item_filename(real_game: GameRoot):
    """D6ITEM.DAT движком не открывается: строки с этим именем в образе нет."""
    exe = real_game.read("dlords.exe").upper()
    assert b"D6ITEM" not in exe
    assert b"ITEM.DAT" not in exe
    # контроль: имена таблиц, которые движок действительно читает
    assert b"D6MONS.DAT" in exe
    assert b"D6TRLIST.DAT" in exe
