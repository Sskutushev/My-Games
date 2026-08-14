from __future__ import annotations

import struct

import pytest

from dl_toolkit.game import GameRoot
from dl_toolkit.itempatch import (
    AppliedPatch,
    ItemPatch,
    PatchError,
    apply_patches,
    plan_patches,
    verify_patches,
)
from dl_toolkit.itemtab import ITEM_ARRAY_BASE, ITEM_STRIDE, MAKEITEMS_VA, extract
from dl_toolkit.pe import PeImage
from tests.test_pe_and_itemtab import IMAGE_BASE, build_pe

pytest.importorskip("capstone")


def synthetic_image() -> PeImage:
    """Мини-MakeITEMS: имя из .rdata, цена как imm32, тип через регистр."""
    code = bytearray()
    # mov dword ptr [BASE + 0], eax  (имя) — сначала загрузим строку
    code += b"\xa1" + struct.pack("<I", IMAGE_BASE + 0x2000)  # mov eax, [str]
    code += b"\xa3" + struct.pack("<I", ITEM_ARRAY_BASE)  # mov [BASE], eax
    # mov dword ptr [BASE + 60], 1000     — цена, патчится
    code += b"\xc7\x05" + struct.pack("<I", ITEM_ARRAY_BASE + 60) + struct.pack("<I", 1000)
    # mov bp, 4 ; mov word ptr [BASE + 32], bp   — тип через регистр, не патчится
    code += b"\x66\xbd" + struct.pack("<H", 4)
    code += b"\x66\x89\x2d" + struct.pack("<I", ITEM_ARRAY_BASE + 32)
    # mov word ptr [BASE + 40], 7          — иконка, патчится (16 бит)
    code += b"\x66\xc7\x05" + struct.pack("<I", ITEM_ARRAY_BASE + 40) + struct.pack("<H", 7)
    code += b"\xc3"

    text_rva = MAKEITEMS_VA - IMAGE_BASE
    return PeImage.parse(
        build_pe(
            [
                (".text", text_rva, len(code) + 16, bytes(code)),
                (".rdata", 0x2000, 0x20, b"TESTBLADE\x00" + b"\x00" * 8),
            ]
        )
    )


@pytest.fixture
def image() -> PeImage:
    return synthetic_image()


def test_synthetic_table_is_reconstructed(image: PeImage):
    table = extract(image)
    assert table.name(0) == "TEST"  # первые 4 байта имени: запись идёт одним dword
    assert table.value(0, "price") == 1000
    assert table.value(0, "type") == 4
    assert table.value(0, "icon") == 7


def test_plan_reports_offsets_without_writing(image: PeImage):
    planned = plan_patches(image, [ItemPatch(0, "price", 5555)])
    assert len(planned) == 1
    entry = planned[0]
    assert isinstance(entry, AppliedPatch)
    assert entry.old_value == 1000
    assert entry.new_value == 5555
    assert entry.width == 4
    # исходный образ не тронут
    assert extract(image).value(0, "price") == 1000


def test_apply_changes_only_the_operand(image: PeImage):
    patched, applied = apply_patches(image, [ItemPatch(0, "price", 5555)])
    changed = [i for i, (a, b) in enumerate(zip(image.data, patched)) if a != b]
    assert len(changed) <= 4
    assert applied[0].file_offset in changed
    assert len(patched) == len(image.data)
    assert not verify_patches(patched, [ItemPatch(0, "price", 5555)])


def test_apply_two_fields_at_once(image: PeImage):
    patches = [ItemPatch(0, "price", 1), ItemPatch(0, "icon", 300)]
    patched, applied = apply_patches(image, patches)
    assert len(applied) == 2
    assert not verify_patches(patched, patches)


def test_verify_detects_mismatch(image: PeImage):
    patched, _ = apply_patches(image, [ItemPatch(0, "price", 42)])
    problems = verify_patches(patched, [ItemPatch(0, "price", 43)])
    assert problems and "ожидалось 43" in problems[0]


def test_register_sourced_field_is_refused(image: PeImage):
    with pytest.raises(PatchError, match="приходит из регистра"):
        apply_patches(image, [ItemPatch(0, "type", 5)])


def test_name_field_is_refused(image: PeImage):
    with pytest.raises(PatchError, match="имя предмета патчить нельзя"):
        apply_patches(image, [ItemPatch(0, "name", 1)])


def test_unknown_field_is_refused(image: PeImage):
    with pytest.raises(PatchError, match="неизвестное поле"):
        apply_patches(image, [ItemPatch(0, "sharpness", 1)])


def test_uninitialised_field_is_refused(image: PeImage):
    with pytest.raises(PatchError, match="не инициализируется в коде"):
        apply_patches(image, [ItemPatch(0, "armor", 10)])


def test_value_overflow_is_refused(image: PeImage):
    with pytest.raises(PatchError, match="не помещается"):
        apply_patches(image, [ItemPatch(0, "icon", 70000)])


def test_negative_value_is_refused(image: PeImage):
    with pytest.raises(PatchError, match="не помещается"):
        apply_patches(image, [ItemPatch(0, "price", -1)])


def test_duplicate_patch_of_same_instruction_is_refused(image: PeImage):
    with pytest.raises(PatchError, match="уже патчится"):
        apply_patches(image, [ItemPatch(0, "price", 1), ItemPatch(0, "price", 2)])


def test_patch_str_is_readable():
    assert str(ItemPatch(3, "price", 10)) == "предмет 3, поле price := 10"


@pytest.mark.gamedata
def test_patch_real_exe_roundtrip(real_game: GameRoot):
    """Патч цены на настоящем образе: меняются только байты операнда."""
    original = real_game.read("dlords.exe")
    image = PeImage.parse(original)
    table = extract(image)

    by_name = {table.name(i): i for i in table.defined_indices()}
    katana = by_name["KATANA"]
    assert table.value(katana, "price") == 1000

    patches = [ItemPatch(katana, "price", 7777)]
    patched, applied = apply_patches(image, patches)

    assert len(patched) == len(original)
    changed = [i for i, (a, b) in enumerate(zip(original, patched)) if a != b]
    assert 0 < len(changed) <= 4
    assert applied[0].width == 4
    assert not verify_patches(patched, patches)

    # остальные предметы не задеты
    after = extract(PeImage.parse(patched))
    for name, index in list(by_name.items())[:50]:
        if index != katana:
            assert after.value(index, "price") == table.value(index, "price"), name


@pytest.mark.gamedata
def test_real_table_field_semantics(real_game: GameRoot):
    """Опорные значения, на которых держится карта полей."""
    table = extract(PeImage.parse(real_game.read("dlords.exe")))
    by_name = {table.name(i): i for i in table.defined_indices()}

    # оружие: навык растёт с весом оружия, урон — тоже
    longsword, greatsword = by_name["LONGSWORD"], by_name["GREATSWORD"]
    assert table.value(longsword, "type") == 1
    assert table.value(longsword, "skill") == 3  # среднее оружие
    assert table.value(greatsword, "skill") == 4  # тяжёлое оружие
    assert table.value(greatsword, "damage") > table.value(longsword, "damage")

    # лук использует навык стрельбы
    assert table.value(by_name["SHORT BOW"], "skill") == 10

    # броня: слот ног отличается от слота рук
    assert table.value(by_name["CHAIN BOOTS"], "slot") == 4
    assert table.value(by_name["CHAIN MITTENS"], "slot") == 3
    assert table.value(by_name["CHAIN BOOTS"], "type") == 4


@pytest.mark.gamedata
def test_real_table_matches_iname(real_game: GameRoot):
    """Соответствие индекса записи и id в iname.dat: 510 из 510."""
    from dl_toolkit.codecs import StringTableCodec

    table = extract(PeImage.parse(real_game.read("dlords.exe")))
    names = StringTableCodec().decode(real_game.read("iname.dat")).as_dict()

    defined = table.defined_indices()
    assert len(defined) == 510
    assert all(names.get(index + 1) == table.name(index) for index in defined)

    # соседние сдвиги дают только случайные совпадения
    shifted = sum(1 for index in defined if names.get(index) == table.name(index))
    assert shifted < 30


def test_stride_and_base_are_documented():
    assert ITEM_STRIDE == 204
    assert ITEM_ARRAY_BASE == 0x030DF40C
