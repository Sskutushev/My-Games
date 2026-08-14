from __future__ import annotations

import struct
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from dl_toolkit.cli import app
from dl_toolkit.game import GameRoot
from dl_toolkit.itemtab import ITEM_ARRAY_BASE, ITEM_STRIDE, MAKEITEMS_VA
from dl_toolkit.pe import PeImage
from tests.test_pe_and_itemtab import IMAGE_BASE, build_pe

pytest.importorskip("capstone")
runner = CliRunner()


def synthetic_exe() -> bytes:
    """Образ с двумя предметами: имена копируются из .rdata по 4 байта, цены — imm32.

    Именно так это выглядит в настоящем ``MakeITEMS``: компилятор разбивает
    строковую константу на dword-пересылки через регистр.
    """
    items = [("KATANA", 1000), ("SHORT BOW", 250)]

    rdata = bytearray()
    name_offsets: list[int] = []
    for name, _ in items:
        name_offsets.append(len(rdata))
        rdata += name.encode() + b"\x00"
        rdata += b"\x00" * (-len(rdata) % 4)

    code = bytearray()
    for index, ((name, price), rdata_offset) in enumerate(zip(items, name_offsets)):
        base = ITEM_ARRAY_BASE + index * ITEM_STRIDE
        for chunk in range((len(name) + 4) // 4):  # +1 на NUL, вверх до кратности 4
            source = IMAGE_BASE + 0x2000 + rdata_offset + chunk * 4
            code += b"\xa1" + struct.pack("<I", source)  # mov eax, [строка]
            code += b"\xa3" + struct.pack("<I", base + chunk * 4)  # mov [запись], eax
        code += b"\xc7\x05" + struct.pack("<I", base + 60) + struct.pack("<I", price)
        code += b"\x66\xc7\x05" + struct.pack("<I", base + 40) + struct.pack("<H", index + 1)
    code += b"\xc3"

    return build_pe(
        [
            (".text", MAKEITEMS_VA - IMAGE_BASE, len(code) + 16, bytes(code)),
            (".rdata", 0x2000, 0x40, bytes(rdata).ljust(0x40, b"\x00")),
        ]
    )


@pytest.fixture
def game_with_items(tmp_path: Path) -> GameRoot:
    for marker in GameRoot.MARKERS:
        (tmp_path / marker).write_bytes(b"stub")
    (tmp_path / "dlords.exe").write_bytes(synthetic_exe())
    return GameRoot(tmp_path)


def test_items_lists_and_exports(game_with_items: GameRoot, tmp_path: Path):
    out = tmp_path / "items.csv"
    result = runner.invoke(
        app,
        ["items", "--game", str(game_with_items.path), "--csv", str(out), "--find", "kat"],
    )
    assert result.exit_code == 0
    assert "KATANA" in result.stdout

    rows = out.read_text("utf-8-sig").splitlines()
    assert rows[0].startswith("index;iname_id;name;")
    assert len(rows) == 3  # заголовок + два предмета
    assert "KATANA" in rows[1]


def test_items_without_options_only_reports(game_with_items: GameRoot):
    result = runner.invoke(app, ["items", "--game", str(game_with_items.path)])
    assert result.exit_code == 0
    assert "записей с характеристиками" in result.stdout


def write_plan(path: Path, patches: list[dict[str, object]]) -> Path:
    path.write_text(yaml.safe_dump({"patches": patches}, allow_unicode=True), "utf-8")
    return path


def test_items_patch_dry_run_then_write(game_with_items: GameRoot, tmp_path: Path):
    plan = write_plan(tmp_path / "plan.yaml", [{"name": "KATANA", "field": "price", "value": 4242}])
    before = game_with_items.read("dlords.exe")

    dry = runner.invoke(app, ["items-patch", str(plan), "--game", str(game_with_items.path)])
    assert dry.exit_code == 0
    assert "сухой прогон" in dry.stdout
    assert game_with_items.read("dlords.exe") == before

    written = runner.invoke(
        app, ["items-patch", str(plan), "--game", str(game_with_items.path), "--write"]
    )
    assert written.exit_code == 0

    from dl_toolkit.itemtab import extract

    table = extract(PeImage.parse(game_with_items.read("dlords.exe")))
    assert table.value(0, "price") == 4242
    assert (game_with_items.backup_dir / "dlords.exe").read_bytes() == before


def test_items_patch_accepts_explicit_index(game_with_items: GameRoot, tmp_path: Path):
    plan = write_plan(tmp_path / "plan.yaml", [{"index": 1, "field": "icon", "value": 9}])
    result = runner.invoke(app, ["items-patch", str(plan), "--game", str(game_with_items.path)])
    assert result.exit_code == 0
    assert "icon" in result.stdout


def test_items_patch_unknown_name_fails(game_with_items: GameRoot, tmp_path: Path):
    plan = write_plan(
        tmp_path / "plan.yaml", [{"name": "НЕТ ТАКОГО", "field": "price", "value": 1}]
    )
    result = runner.invoke(app, ["items-patch", str(plan), "--game", str(game_with_items.path)])
    assert result.exit_code == 1
    assert "не найден" in result.stdout


def test_items_patch_rejects_impossible_patch(game_with_items: GameRoot, tmp_path: Path):
    plan = write_plan(tmp_path / "plan.yaml", [{"name": "KATANA", "field": "armor", "value": 5}])
    result = runner.invoke(app, ["items-patch", str(plan), "--game", str(game_with_items.path)])
    assert result.exit_code == 1
    assert "не инициализируется" in result.stdout


def test_items_patch_empty_plan(game_with_items: GameRoot, tmp_path: Path):
    plan = write_plan(tmp_path / "plan.yaml", [])
    result = runner.invoke(app, ["items-patch", str(plan), "--game", str(game_with_items.path)])
    assert result.exit_code == 0
    assert "нет патчей" in result.stdout


def test_shipped_example_plan_is_valid_yaml():
    path = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "obsidian_gate"
        / "item_patches.example.yaml"
    )
    document = yaml.safe_load(path.read_text("utf-8"))
    assert document["patches"]
    for entry in document["patches"]:
        assert "field" in entry
        assert "value" in entry
        assert "name" in entry or "index" in entry
