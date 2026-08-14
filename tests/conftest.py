"""Общие фикстуры."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dl_toolkit.game import GameRoot


@pytest.fixture
def fake_game(tmp_path: Path) -> GameRoot:
    """Минимальная установка, проходящая распознавание корня."""
    for marker in GameRoot.MARKERS:
        (tmp_path / marker).write_bytes(b"stub")
    (tmp_path / "npccode").mkdir()
    return GameRoot(tmp_path)


@pytest.fixture
def real_game() -> GameRoot:
    """Настоящая установка игры; тест пропускается, если её нет."""
    env = os.environ.get("DL_GAME_ROOT")
    if not env or not GameRoot._looks_like_game(Path(env)):
        pytest.skip("DL_GAME_ROOT не задан или не указывает на установку DEEP6")
    return GameRoot(Path(env).resolve())


@pytest.fixture
def ruleset_path() -> Path:
    path = Path(__file__).resolve().parent.parent / "data" / "obsidian_gate" / "ruleset.yaml"
    if not path.is_file():
        pytest.skip("свод правил не сгенерирован: python tools/generate_ruleset.py")
    return path
