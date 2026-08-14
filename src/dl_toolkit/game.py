"""Доступ к установленной игре: поиск корня, чтение и безопасная запись.

Правила записи, встроенные в слой:

1. Перед первой записью файла создаётся резервная копия в ``.dl_backup/``.
2. Запись идёт через временный файл и атомарную замену.
3. Каждая операция пишется в манифест с хешами до и после.

Без этих трёх пунктов любая ошибка кодека уничтожает установку без возможности
отката.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

BACKUP_DIR = ".dl_backup"
MANIFEST = "manifest.json"


class GameNotFoundError(RuntimeError):
    """Каталог игры не найден или не похож на установку DEEP6."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(slots=True)
class GameRoot:
    """Корень установленной игры."""

    path: Path

    #: Файлы, по наличию которых распознаётся установка DEEP6.
    MARKERS = ("dlords.exe", "D6ITEM.DAT", "rd6string.dat")

    @classmethod
    def discover(cls, explicit: str | os.PathLike[str] | None = None) -> GameRoot:
        """Найти корень игры.

        Явно указанный путь авторитетен: если он не похож на установку, это
        ошибка, а не повод молча взять другой каталог. Иначе пробуются
        ``DL_GAME_ROOT`` и текущий каталог.
        """
        if explicit is not None:
            candidate = Path(explicit)
            if cls._looks_like_game(candidate):
                return cls(candidate.resolve())
            raise GameNotFoundError(
                f"{candidate} не похож на установку DEEP6: нет файлов {', '.join(cls.MARKERS)}"
            )

        candidates: list[Path] = []
        env = os.environ.get("DL_GAME_ROOT")
        if env:
            candidates.append(Path(env))
        candidates.append(Path.cwd())

        for candidate in candidates:
            if cls._looks_like_game(candidate):
                return cls(candidate.resolve())
        raise GameNotFoundError(
            "не найден корень игры; укажите путь явно или задайте DL_GAME_ROOT "
            f"(проверены: {', '.join(str(c) for c in candidates)})"
        )

    @classmethod
    def _looks_like_game(cls, path: Path) -> bool:
        return path.is_dir() and all((path / marker).is_file() for marker in cls.MARKERS)

    @property
    def backup_dir(self) -> Path:
        return self.path / BACKUP_DIR

    def read(self, relative: str) -> bytes:
        target = self.path / relative
        if not target.is_file():
            raise FileNotFoundError(f"нет файла {relative} в {self.path}")
        return target.read_bytes()

    def exists(self, relative: str) -> bool:
        return (self.path / relative).is_file()

    def glob(self, pattern: str) -> list[Path]:
        return sorted(self.path.glob(pattern))

    def backup(self, relative: str) -> Path:
        """Сохранить оригинал, если копии ещё нет. Повторный вызов не перезаписывает."""
        source = self.path / relative
        destination = self.backup_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(source, destination)
        return destination

    def restore(self, relative: str) -> None:
        """Вернуть файл из резервной копии."""
        source = self.backup_dir / relative
        if not source.is_file():
            raise FileNotFoundError(f"нет резервной копии для {relative}")
        shutil.copy2(source, self.path / relative)

    def write(self, relative: str, data: bytes) -> None:
        """Атомарно записать файл, предварительно сохранив оригинал."""
        target = self.path / relative
        before = target.read_bytes() if target.is_file() else b""
        if target.is_file():
            self.backup(relative)

        temporary = target.with_suffix(target.suffix + ".dl_tmp")
        temporary.write_bytes(data)
        temporary.replace(target)
        self._record(relative, sha256(before) if before else None, sha256(data), len(data))

    def _record(self, relative: str, before: str | None, after: str, size: int) -> None:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = self.backup_dir / MANIFEST
        entries: list[dict[str, object]] = []
        if manifest_path.is_file():
            entries = json.loads(manifest_path.read_text("utf-8"))
        entries.append(
            {
                "file": relative,
                "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
                "sha256_before": before,
                "sha256_after": after,
                "bytes": size,
            }
        )
        manifest_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), "utf-8")

    def manifest(self) -> list[dict[str, object]]:
        manifest_path = self.backup_dir / MANIFEST
        if not manifest_path.is_file():
            return []
        data: list[dict[str, object]] = json.loads(manifest_path.read_text("utf-8"))
        return data
