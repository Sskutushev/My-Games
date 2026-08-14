from __future__ import annotations

import os
from pathlib import Path

import pytest

from dl_toolkit.game import GameNotFoundError, GameRoot, sha256
from dl_toolkit.verify import summarize, verify_all


def test_discover_explicit_path(fake_game: GameRoot):
    assert GameRoot.discover(fake_game.path).path == fake_game.path.resolve()


def test_discover_from_env(fake_game: GameRoot, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DL_GAME_ROOT", str(fake_game.path))
    assert GameRoot.discover().path == fake_game.path.resolve()


def test_discover_failure_lists_candidates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DL_GAME_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(GameNotFoundError, match="не найден корень игры"):
        GameRoot.discover()


def test_explicit_path_does_not_fall_back_to_env(
    tmp_path: Path, fake_game: GameRoot, monkeypatch: pytest.MonkeyPatch
):
    """Явный --game авторитетен: молчаливый откат на другой каталог недопустим."""
    monkeypatch.setenv("DL_GAME_ROOT", str(fake_game.path))
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(GameNotFoundError, match="не похож на установку DEEP6"):
        GameRoot.discover(empty)


def test_read_missing_file(fake_game: GameRoot):
    assert fake_game.exists("dlords.exe")
    assert not fake_game.exists("nope.dat")
    with pytest.raises(FileNotFoundError, match="нет файла"):
        fake_game.read("nope.dat")


def test_write_creates_backup_and_manifest(fake_game: GameRoot):
    original = fake_game.read("D6ITEM.DAT")
    fake_game.write("D6ITEM.DAT", b"patched")

    assert fake_game.read("D6ITEM.DAT") == b"patched"
    assert (fake_game.backup_dir / "D6ITEM.DAT").read_bytes() == original

    manifest = fake_game.manifest()
    assert len(manifest) == 1
    assert manifest[0]["file"] == "D6ITEM.DAT"
    assert manifest[0]["sha256_before"] == sha256(original)
    assert manifest[0]["sha256_after"] == sha256(b"patched")
    assert manifest[0]["bytes"] == 7


def test_backup_is_not_overwritten_by_second_write(fake_game: GameRoot):
    original = fake_game.read("D6ITEM.DAT")
    fake_game.write("D6ITEM.DAT", b"first")
    fake_game.write("D6ITEM.DAT", b"second")
    assert (fake_game.backup_dir / "D6ITEM.DAT").read_bytes() == original
    assert len(fake_game.manifest()) == 2


def test_restore_returns_original(fake_game: GameRoot):
    original = fake_game.read("D6ITEM.DAT")
    fake_game.write("D6ITEM.DAT", b"broken")
    fake_game.restore("D6ITEM.DAT")
    assert fake_game.read("D6ITEM.DAT") == original


def test_restore_without_backup_raises(fake_game: GameRoot):
    with pytest.raises(FileNotFoundError, match="нет резервной копии"):
        fake_game.restore("D6ITEM.DAT")


def test_write_new_file_records_null_before(fake_game: GameRoot):
    fake_game.write("brand_new.dat", b"x")
    assert fake_game.manifest()[0]["sha256_before"] is None


def test_manifest_empty_before_any_write(fake_game: GameRoot):
    assert fake_game.manifest() == []


def test_glob(fake_game: GameRoot):
    (fake_game.path / "npccode" / "CODEFILE.001").write_bytes(b"")
    (fake_game.path / "npccode" / "CODEFILE.002").write_bytes(b"")
    assert [p.name for p in fake_game.glob("npccode/CODEFILE.*")] == [
        "CODEFILE.001",
        "CODEFILE.002",
    ]


def test_verify_reports_failures_on_stub_installation(fake_game: GameRoot):
    results = verify_all(fake_game)
    ok, total = summarize(results)
    assert total > 0
    assert ok == 0
    assert all(not r.ok for r in results)
    assert {r.status for r in results} == {"FAIL"}
    assert any("нет файла" in r.detail for r in results)


@pytest.mark.gamedata
def test_roundtrip_against_real_installation(real_game: GameRoot):
    """Главная гарантия проекта: все поддерживаемые файлы пишутся байт-в-байт."""
    results = verify_all(real_game)
    failures = [f"{r.file}: {r.detail}" for r in results if not r.ok]
    assert not failures, "round-trip нарушен:\n" + "\n".join(failures)
    assert len(results) > 160


@pytest.mark.gamedata
def test_script_limit_reduces_workload(real_game: GameRoot):
    assert len(verify_all(real_game, script_limit=1)) < len(verify_all(real_game))


@pytest.mark.skipif(os.name != "nt", reason="проверка атомарной замены на Windows")
def test_temporary_file_is_cleaned_up(fake_game: GameRoot):
    fake_game.write("D6ITEM.DAT", b"payload")
    assert not list(fake_game.path.glob("*.dl_tmp"))
