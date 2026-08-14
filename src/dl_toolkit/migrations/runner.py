"""Миграции схемы данных дизайна.

Файлы в ``data/`` живут дольше кода: правила меняются, поля переименовываются,
структуры разъезжаются. Чтобы старые файлы не приходилось править вручную,
каждая версия схемы получает функцию перехода ``vN -> vN+1``.

Правила:

* миграция чистая — принимает документ, возвращает новый, не трогает диск;
* миграции применяются последовательно, пропуски запрещены;
* понижение версии не поддерживается: откат делается через git.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from dl_toolkit.content.loader import CURRENT_SCHEMA_VERSION

Document = dict[str, Any]
Migration = Callable[[Document], Document]


class MigrationError(RuntimeError):
    """Документ невозможно привести к текущей версии схемы."""


def _v1_to_v2(document: Document) -> Document:
    """v1 → v2: разделение имени класса на ``name_ru``/``name_en``.

    В v1 у классов и рас было единственное поле ``name``. Локализация требует
    двух, поэтому старое значение становится русским именем, а английское
    выводится из ключа.
    """
    result = deepcopy(document)
    for section in ("races", "classes"):
        for entry in result.get(section, []):
            if "name" in entry and "name_ru" not in entry:
                entry["name_ru"] = entry.pop("name")
            entry.setdefault("name_en", entry.get("key", "").replace("_", " ").title())
    result["schema_version"] = 2
    return result


#: Реестр переходов: ключ — версия «из».
MIGRATIONS: dict[int, Migration] = {
    1: _v1_to_v2,
}


def migrate_document(document: Document) -> Document:
    """Привести документ к :data:`CURRENT_SCHEMA_VERSION`."""
    version = document.get("schema_version")
    if version is None:
        raise MigrationError("в документе нет поля schema_version")
    if not isinstance(version, int):
        raise MigrationError(f"schema_version должен быть целым, получено {version!r}")
    if version > CURRENT_SCHEMA_VERSION:
        raise MigrationError(
            f"документ версии {version} новее поддерживаемой {CURRENT_SCHEMA_VERSION}: "
            "обновите dl-toolkit"
        )

    current = document
    while version < CURRENT_SCHEMA_VERSION:
        migration = MIGRATIONS.get(version)
        if migration is None:
            raise MigrationError(f"нет миграции с версии {version} на {version + 1}")
        current = migration(current)
        new_version = current.get("schema_version")
        if new_version != version + 1:
            raise MigrationError(
                f"миграция {version}->{version + 1} выставила версию {new_version}"
            )
        version = new_version
    return current


def pending(document: Document) -> list[int]:
    """Список версий, через которые ещё предстоит пройти."""
    version = document.get("schema_version", CURRENT_SCHEMA_VERSION)
    if not isinstance(version, int):
        return []
    return list(range(version, CURRENT_SCHEMA_VERSION))
