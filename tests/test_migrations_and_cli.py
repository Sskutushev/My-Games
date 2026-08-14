from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from dl_toolkit.cli import app
from dl_toolkit.content import CURRENT_SCHEMA_VERSION
from dl_toolkit.game import GameRoot
from dl_toolkit.migrations import MigrationError, migrate_document, pending

runner = CliRunner()


# ------------------------------------------------------------------ миграции


def v1_document() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "title_ru": "Тест",
        "title_en": "Test",
        "races": [{"slot": 0, "key": "virn", "name": "Вирн", "attributes": {}}],
        "classes": [{"slot": 1, "key": "steel_lord", "name": "Владыка Стали", "tier": "base"}],
    }


def test_migrate_v1_to_v2_splits_name():
    result = migrate_document(v1_document())
    assert result["schema_version"] == 2
    assert result["races"][0]["name_ru"] == "Вирн"
    assert result["races"][0]["name_en"] == "Virn"
    assert result["classes"][0]["name_ru"] == "Владыка Стали"
    assert result["classes"][0]["name_en"] == "Steel Lord"


def test_migrate_does_not_mutate_input():
    document = v1_document()
    migrate_document(document)
    assert document["schema_version"] == 1
    assert "name" in document["races"][0]


def test_migrate_is_idempotent_at_current_version():
    current = {"schema_version": CURRENT_SCHEMA_VERSION}
    assert migrate_document(current) is current


def test_pending_lists_remaining_versions():
    assert pending({"schema_version": 1}) == [1]
    assert pending({"schema_version": CURRENT_SCHEMA_VERSION}) == []
    assert pending({"schema_version": "нет"}) == []


def test_migrate_error_cases():
    with pytest.raises(MigrationError, match="нет поля schema_version"):
        migrate_document({})
    with pytest.raises(MigrationError, match="должен быть целым"):
        migrate_document({"schema_version": "1"})
    with pytest.raises(MigrationError, match="новее поддерживаемой"):
        migrate_document({"schema_version": CURRENT_SCHEMA_VERSION + 5})


def test_missing_migration_step_is_reported(monkeypatch: pytest.MonkeyPatch):
    from dl_toolkit.migrations import runner as migration_runner

    monkeypatch.setattr(migration_runner, "MIGRATIONS", {})
    with pytest.raises(MigrationError, match="нет миграции"):
        migration_runner.migrate_document({"schema_version": 1})


def test_migration_that_forgets_to_bump_version_is_caught(monkeypatch: pytest.MonkeyPatch):
    from dl_toolkit.migrations import runner as migration_runner

    monkeypatch.setattr(migration_runner, "MIGRATIONS", {1: lambda d: dict(d)})
    with pytest.raises(MigrationError, match="выставила версию"):
        migration_runner.migrate_document({"schema_version": 1})


# ------------------------------------------------------------------ CLI


def test_cli_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "dl-toolkit" in result.stdout


def test_cli_rules_reports_summary(ruleset_path: Path):
    result = runner.invoke(app, ["rules", str(ruleset_path), "--matrix"])
    assert result.exit_code == 0
    assert "Обсидиановые Врата" in result.stdout


def test_cli_migrate_dry_run_and_write(tmp_path: Path):
    path = tmp_path / "rules.yaml"
    path.write_text(yaml.safe_dump(v1_document(), allow_unicode=True), "utf-8")

    dry = runner.invoke(app, ["migrate", str(path)])
    assert dry.exit_code == 0
    assert "сухой прогон" in dry.stdout
    assert yaml.safe_load(path.read_text("utf-8"))["schema_version"] == 1

    written = runner.invoke(app, ["migrate", str(path), "--write"])
    assert written.exit_code == 0
    assert yaml.safe_load(path.read_text("utf-8"))["schema_version"] == 2


def test_cli_migrate_noop(tmp_path: Path):
    path = tmp_path / "rules.yaml"
    path.write_text(yaml.safe_dump({"schema_version": CURRENT_SCHEMA_VERSION}), "utf-8")
    result = runner.invoke(app, ["migrate", str(path)])
    assert result.exit_code == 0
    assert "не требуются" in result.stdout


def test_cli_verify_fails_on_stub_installation(fake_game: GameRoot):
    result = runner.invoke(app, ["verify", "--game", str(fake_game.path)])
    assert result.exit_code == 1
    assert "round-trip" in result.stdout


def test_cli_reports_missing_game(tmp_path: Path):
    result = runner.invoke(app, ["verify", "--game", str(tmp_path)])
    assert result.exit_code == 2


def test_cli_restore(fake_game: GameRoot):
    original = fake_game.read("D6ITEM.DAT")
    fake_game.write("D6ITEM.DAT", b"broken")
    result = runner.invoke(app, ["restore", "D6ITEM.DAT", "--game", str(fake_game.path)])
    assert result.exit_code == 0
    assert fake_game.read("D6ITEM.DAT") == original


@pytest.mark.gamedata
def test_cli_verify_and_capacity_on_real_game(real_game: GameRoot):
    verify = runner.invoke(app, ["verify", "--game", str(real_game.path)])
    assert verify.exit_code == 0

    capacity = runner.invoke(app, ["capacity", "--game", str(real_game.path)])
    assert capacity.exit_code == 0
    assert "D6TRLIST.DAT" in capacity.stdout
