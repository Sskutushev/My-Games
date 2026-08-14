"""Предметная модель тотальной конверсии «Обсидиановые Врата».

Движок DEEP6 закрыт, поэтому каркас неподвижен и задаёт жёсткие рамки:

* 6 атрибутов;
* 16 слотов рас (``rd6string.dat`` 1300–1315);
* 35 слотов классов (1400–1434), из них 1400 — «нет класса»;
* 45 слотов навыков (1800–1844);
* 4 школы магии.

Дизайн новой игры обязан укладываться ровно в эти числа. Модель ниже
валидирует это на уровне типов и проверок, чтобы несоответствие всплывало при
сборке, а не после записи в игру.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from itertools import pairwise

ATTRIBUTE_SLOTS = 6
RACE_SLOTS = 16
CLASS_SLOTS = 35
SKILL_SLOTS = 45

RACE_STRING_BASE = 1300
CLASS_STRING_BASE = 1400
SKILL_STRING_BASE = 1800


class Attribute(StrEnum):
    """Шесть атрибутов движка. Порядок соответствует id 1100–1105."""

    STRENGTH = "strength"
    INTELLECT = "intellect"
    DEXTERITY = "dexterity"
    AGILITY = "agility"
    VITALITY = "vitality"
    HONOR = "honor"


class MagicSchool(StrEnum):
    """Четыре школы. Слоты навыков 1830–1833 в движке."""

    ARCANE = "arcane"
    CELESTIAL = "celestial"
    NETHER = "nether"
    RUNE = "rune"


class SkillGroup(StrEnum):
    MELEE = "melee"
    RANGED = "ranged"
    DEFENSE = "defense"
    MOVEMENT = "movement"
    LARCENY = "larceny"
    MAGIC = "magic"
    CRAFT = "craft"
    PASSIVE = "passive"


class ClassTier(StrEnum):
    """Ступени продвижения. Совпадают с аргументом ``setclass(tier)`` в скриптах NPC."""

    NONE = "none"
    BASE = "base"
    SPECIALIST = "specialist"
    VETERAN = "veteran"
    ELITE = "elite"


class ItemGrade(StrEnum):
    """Градации снаряжения. Реализуются через поле качества в ``D6ITEM.DAT``."""

    CRUDE = "crude"
    LEATHER = "leather"
    MAIL = "mail"
    PLATE = "plate"
    RUNIC = "runic"
    OBSIDIAN = "obsidian"


class ValidationError(ValueError):
    """Данные дизайна нарушают ограничение движка."""


@dataclass(frozen=True, slots=True)
class Race:
    """Играбельная раса."""

    slot: int
    key: str
    name_ru: str
    name_en: str
    base_attributes: dict[Attribute, int]
    life: int
    speed_bonus: int
    parry_bonus: int
    playable: bool
    summary: str

    @property
    def string_id(self) -> int:
        return RACE_STRING_BASE + self.slot

    def validate(self) -> None:
        if not 0 <= self.slot < RACE_SLOTS:
            raise ValidationError(f"раса {self.key}: слот {self.slot} вне 0..{RACE_SLOTS - 1}")
        missing = set(Attribute) - set(self.base_attributes)
        if missing:
            raise ValidationError(
                f"раса {self.key}: не заданы атрибуты {', '.join(sorted(missing))}"
            )
        for attribute, value in self.base_attributes.items():
            if not 1 <= value <= 30:
                raise ValidationError(
                    f"раса {self.key}: {attribute} = {value} вне разумного диапазона 1..30"
                )


@dataclass(frozen=True, slots=True)
class Skill:
    """Навык. Слот жёстко привязан к механике внутри ``dlords.exe``."""

    slot: int
    key: str
    name_ru: str
    group: SkillGroup
    engine_behaviour: str
    requires: tuple[str, ...] = ()

    @property
    def string_id(self) -> int:
        return SKILL_STRING_BASE + self.slot

    def validate(self) -> None:
        if not 0 <= self.slot < SKILL_SLOTS:
            raise ValidationError(f"навык {self.key}: слот {self.slot} вне 0..{SKILL_SLOTS - 1}")


@dataclass(frozen=True, slots=True)
class SkillAccess:
    """Доступ класса к навыку: предел развития и ступень открытия."""

    skill: str
    cap: int
    unlock_tier: ClassTier

    def validate(self, class_key: str) -> None:
        if not 0 <= self.cap <= 10:
            raise ValidationError(
                f"класс {class_key}, навык {self.skill}: предел {self.cap} вне 0..10"
            )


@dataclass(frozen=True, slots=True)
class CharacterClass:
    """Класс персонажа."""

    slot: int
    key: str
    name_ru: str
    name_en: str
    tier: ClassTier
    guild: str
    parent: str | None
    requirements: dict[Attribute, int]
    required_level: int
    quest_register: str | None
    skills: tuple[SkillAccess, ...] = ()
    summary: str = ""

    @property
    def string_id(self) -> int:
        return CLASS_STRING_BASE + self.slot

    def validate(self) -> None:
        if not 0 <= self.slot < CLASS_SLOTS:
            raise ValidationError(f"класс {self.key}: слот {self.slot} вне 0..{CLASS_SLOTS - 1}")
        if self.tier is not ClassTier.NONE and not self.name_ru:
            raise ValidationError(f"класс {self.key}: пустое имя")
        if self.tier in (ClassTier.SPECIALIST, ClassTier.VETERAN, ClassTier.ELITE):
            if self.parent is None:
                raise ValidationError(
                    f"класс {self.key}: у ступени {self.tier} должен быть родитель"
                )
            if not self.requirements:
                raise ValidationError(f"класс {self.key}: не заданы требования по атрибутам")
        for access in self.skills:
            access.validate(self.key)


@dataclass(frozen=True, slots=True)
class LevelStep:
    """Одна ступень прогрессии."""

    level: int
    total_xp: int
    attribute_points: int
    skill_points: int

    def validate(self) -> None:
        if self.level < 1:
            raise ValidationError(f"уровень {self.level} должен быть >= 1")
        if self.total_xp < 0:
            raise ValidationError(f"уровень {self.level}: отрицательный опыт")


@dataclass(slots=True)
class ProgressionCurve:
    """Кривая опыта и очков развития."""

    steps: list[LevelStep] = field(default_factory=list)

    @property
    def max_level(self) -> int:
        return max((s.level for s in self.steps), default=0)

    def xp_for(self, level: int) -> int:
        for step in self.steps:
            if step.level == level:
                return step.total_xp
        raise KeyError(f"уровня {level} нет в кривой")

    def level_at(self, xp: int) -> int:
        """Максимальный уровень, достижимый при данном суммарном опыте."""
        reached = 0
        for step in sorted(self.steps, key=lambda s: s.level):
            if xp >= step.total_xp:
                reached = step.level
        return reached

    def validate(self) -> None:
        if not self.steps:
            raise ValidationError("кривая прогрессии пуста")
        ordered = sorted(self.steps, key=lambda s: s.level)
        levels = [s.level for s in ordered]
        if levels != list(range(1, len(levels) + 1)):
            raise ValidationError("уровни должны идти подряд начиная с 1")
        for previous, current in pairwise(ordered):
            if current.total_xp <= previous.total_xp:
                raise ValidationError(
                    f"опыт не растёт: уровень {current.level} требует "
                    f"{current.total_xp}, уровень {previous.level} — {previous.total_xp}"
                )
        for step in ordered:
            step.validate()


@dataclass(slots=True)
class Ruleset:
    """Полный свод правил новой игры."""

    title_ru: str
    title_en: str
    races: list[Race] = field(default_factory=list)
    skills: list[Skill] = field(default_factory=list)
    classes: list[CharacterClass] = field(default_factory=list)
    progression: ProgressionCurve = field(default_factory=ProgressionCurve)

    def validate(self) -> None:
        """Проверить весь свод против ограничений движка."""
        for race in self.races:
            race.validate()
        for skill in self.skills:
            skill.validate()
        for character_class in self.classes:
            character_class.validate()
        self.progression.validate()

        self._check_unique("раса", [r.slot for r in self.races])
        self._check_unique("класс", [c.slot for c in self.classes])
        self._check_unique("навык", [s.slot for s in self.skills])

        skill_keys = {s.key for s in self.skills}
        for character_class in self.classes:
            for access in character_class.skills:
                if access.skill not in skill_keys:
                    raise ValidationError(
                        f"класс {character_class.key} ссылается на неизвестный навык {access.skill}"
                    )
        class_keys = {c.key for c in self.classes}
        for character_class in self.classes:
            if character_class.parent and character_class.parent not in class_keys:
                raise ValidationError(
                    f"класс {character_class.key}: неизвестный родитель {character_class.parent}"
                )

    @staticmethod
    def _check_unique(label: str, slots: list[int]) -> None:
        duplicates = {slot for slot in slots if slots.count(slot) > 1}
        if duplicates:
            raise ValidationError(f"{label}: слоты заняты дважды: {sorted(duplicates)}")

    def playable_races(self) -> list[Race]:
        return [r for r in self.races if r.playable]

    def classes_by_tier(self, tier: ClassTier) -> list[CharacterClass]:
        return [c for c in self.classes if c.tier is tier]

    def skill_matrix(self) -> dict[str, dict[str, int]]:
        """``класс -> навык -> предел``. Нули опускаются."""
        return {
            c.key: {a.skill: a.cap for a in c.skills if a.cap > 0} for c in self.classes if c.skills
        }
