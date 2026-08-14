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


def test_field_write_patchability():
    immediate = FieldWrite(0, 60, 4, 750, 0x1000, "imm")
    from_register = FieldWrite(0, 32, 2, 4, 0x1010, "reg")
    assert immediate.patchable
    assert not from_register.patchable


def test_item_table_accessors_and_bounds():
    table = ItemTable()
    table.memory[60:64] = (750).to_bytes(4, "little")
    table.memory[ITEM_STRIDE : ITEM_STRIDE + 5] = b"AXE\x00\x00"
    table.writes.append(FieldWrite(0, 60, 4, 750, 0x1000, "imm"))

    assert table.value(0, "price") == 750
    assert table.value(0, 60) == 750
    assert table.name(1) == "AXE"
    assert table.defined_indices() == [1]
    assert table.writes_for(0, 60)[0].value == 750
    assert table.writes_for(0, 40) == []
    assert table.as_dict(1)["iname_id"] == 2

    with pytest.raises(IndexError, match="вне 0"):
        table.raw(ITEM_COUNT)
    with pytest.raises(KeyError, match="неизвестное поле"):
        table.value(0, "нет_такого")
    # неизвестное числовое смещение допускается как поле шириной 2
    assert table.value(0, 150) == 0


def test_extract_on_synthetic_makeitems():
    """Синтетический MakeITEMS: непосредственное значение и значение из регистра."""
    pytest.importorskip("capstone")

    code = bytearray()
    # mov dword ptr [BASE + 60], 0x2A   — цена, непосредственный операнд
    code += b"\xc7\x05" + struct.pack("<I", ITEM_ARRAY_BASE + 60) + struct.pack("<I", 0x2A)
    # mov bp, 4 ; mov word ptr [BASE + STRIDE + 32], bp — тип через регистр
    code += b"\x66\xbd" + struct.pack("<H", 4)
    code += b"\x66\x89\x2d" + struct.pack("<I", ITEM_ARRAY_BASE + ITEM_STRIDE + 32)
    code += b"\xc3"

    text_rva = MAKEITEMS_VA - IMAGE_BASE
    image = PeImage.parse(build_pe([(".text", text_rva, len(code) + 16, bytes(code))]))
    table = extract(image)

    assert table.value(0, "price") == 0x2A
    assert table.value(1, "type") == 4
    kinds = {w.kind for w in table.writes}
    assert kinds == {"imm", "reg"}


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

    assert table.instructions > 19_000
    assert len(table.writes) > 10_000
    indices = {write.item_index for write in table.writes}
    assert min(indices) == 0
    assert max(indices) == ITEM_COUNT - 1

    # iname.dat объявляет ровно столько же предметов
    from dl_toolkit.codecs import StringTableCodec

    names = StringTableCodec().decode(real_game.read("iname.dat"))
    assert len(names) == ITEM_COUNT

    # соответствие индекса и id: iname_id = index + 1
    lookup = names.as_dict()
    assert lookup[1] == "PUNCH"
    assert lookup[4] == "CHAIN BOOTS"
    assert table.name(0) == "PUNCH"
    assert table.name(3) == "CHAIN BOOTS"


@pytest.mark.gamedata
def test_real_exe_has_no_d6item_filename(real_game: GameRoot):
    """D6ITEM.DAT движком не открывается: строки с этим именем в образе нет."""
    exe = real_game.read("dlords.exe").upper()
    assert b"D6ITEM" not in exe
    assert b"ITEM.DAT" not in exe
    # контроль: имена таблиц, которые движок действительно читает
    assert b"D6MONS.DAT" in exe
    assert b"D6TRLIST.DAT" in exe
