"""Загрузка свода правил из YAML.

Источник истины дизайна — человекочитаемые YAML-файлы в ``data/``, а не двоичные
файлы игры. Сборка идёт в одну сторону: YAML → валидация → патч игры. Обратное
направление не поддерживается намеренно: правки прямо в игре потерялись бы при
следующей сборке.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from dl_toolkit.content.models import (
    Attribute,
    CharacterClass,
    ClassTier,
    LevelStep,
    ProgressionCurve,
    Race,
    Ruleset,
    Skill,
    SkillAccess,
    SkillGroup,
    ValidationError,
)

#: Версия схемы данных дизайна. Файлы с меньшей версией прогоняются через миграции.
CURRENT_SCHEMA_VERSION = 2


def _require(mapping: dict[str, Any], key: str, context: str) -> Any:
    if key not in mapping:
        raise ValidationError(f"{context}: отсутствует обязательное поле {key!r}")
    return mapping[key]


def _attributes(raw: dict[str, int], context: str) -> dict[Attribute, int]:
    out: dict[Attribute, int] = {}
    for key, value in raw.items():
        try:
            out[Attribute(key)] = int(value)
        except ValueError as exc:
            raise ValidationError(f"{context}: неизвестный атрибут {key!r}") from exc
    return out


def parse_ruleset(document: dict[str, Any]) -> Ruleset:
    """Разобрать уже смигрированный документ в :class:`Ruleset`."""
    version = document.get("schema_version")
    if version != CURRENT_SCHEMA_VERSION:
        raise ValidationError(
            f"версия схемы {version} != текущей {CURRENT_SCHEMA_VERSION}; выполните миграции"
        )

    ruleset = Ruleset(
        title_ru=_require(document, "title_ru", "корень"),
        title_en=_require(document, "title_en", "корень"),
    )

    for raw in document.get("races", []):
        key = _require(raw, "key", "раса")
        ruleset.races.append(
            Race(
                slot=int(_require(raw, "slot", f"раса {key}")),
                key=key,
                name_ru=_require(raw, "name_ru", f"раса {key}"),
                name_en=raw.get("name_en", ""),
                base_attributes=_attributes(
                    _require(raw, "attributes", f"раса {key}"), f"раса {key}"
                ),
                life=int(raw.get("life", 0)),
                speed_bonus=int(raw.get("speed_bonus", 0)),
                parry_bonus=int(raw.get("parry_bonus", 0)),
                playable=bool(raw.get("playable", True)),
                summary=raw.get("summary", ""),
            )
        )

    for raw in document.get("skills", []):
        key = _require(raw, "key", "навык")
        ruleset.skills.append(
            Skill(
                slot=int(_require(raw, "slot", f"навык {key}")),
                key=key,
                name_ru=_require(raw, "name_ru", f"навык {key}"),
                group=SkillGroup(_require(raw, "group", f"навык {key}")),
                engine_behaviour=raw.get("engine_behaviour", ""),
                requires=tuple(raw.get("requires", ())),
            )
        )

    for raw in document.get("classes", []):
        key = _require(raw, "key", "класс")
        ruleset.classes.append(
            CharacterClass(
                slot=int(_require(raw, "slot", f"класс {key}")),
                key=key,
                name_ru=_require(raw, "name_ru", f"класс {key}"),
                name_en=raw.get("name_en", ""),
                tier=ClassTier(_require(raw, "tier", f"класс {key}")),
                guild=raw.get("guild", ""),
                parent=raw.get("parent"),
                requirements=_attributes(raw.get("requirements", {}), f"класс {key}"),
                required_level=int(raw.get("required_level", 1)),
                quest_register=raw.get("quest_register"),
                skills=tuple(
                    SkillAccess(
                        skill=_require(access, "skill", f"класс {key}"),
                        cap=int(_require(access, "cap", f"класс {key}")),
                        unlock_tier=ClassTier(access.get("unlock_tier", "base")),
                    )
                    for access in raw.get("skills", [])
                ),
                summary=raw.get("summary", ""),
            )
        )

    curve = ProgressionCurve()
    for raw in document.get("progression", []):
        curve.steps.append(
            LevelStep(
                level=int(_require(raw, "level", "прогрессия")),
                total_xp=int(_require(raw, "total_xp", "прогрессия")),
                attribute_points=int(raw.get("attribute_points", 0)),
                skill_points=int(raw.get("skill_points", 0)),
            )
        )
    ruleset.progression = curve
    return ruleset


def load_ruleset(path: str | Path, *, migrate: bool = True) -> Ruleset:
    """Прочитать YAML, при необходимости смигрировать и провалидировать."""
    document = yaml.safe_load(Path(path).read_text("utf-8"))
    if not isinstance(document, dict):
        raise ValidationError(f"{path}: ожидался словарь на верхнем уровне")
    if migrate:
        from dl_toolkit.migrations.runner import migrate_document

        document = migrate_document(document)
    ruleset = parse_ruleset(document)
    ruleset.validate()
    return ruleset
