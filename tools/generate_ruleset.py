"""Генератор свода правил «Обсидиановые Врата».

Матрица «35 классов x 45 навыков» слишком велика для ручного ведения: 1575
ячеек, каждая из которых должна согласовываться с гильдией, ступенью и
родительским классом. Поэтому матрица выводится из компактных правил, а YAML —
артефакт сборки, который коммитится и валидируется в CI.

Запуск::

    python tools/generate_ruleset.py

Результат: ``data/obsidian_gate/ruleset.yaml``
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "obsidian_gate" / "ruleset.yaml"

# --------------------------------------------------------------------------- расы
# Слоты 0..15 жёстко заданы движком (rd6string.dat 1300-1315). Играбельными
# оставлены пять: остальные одиннадцать помечены как неиграбельные, их строки
# затираются служебной заглушкой.
RACES: list[dict[str, Any]] = [
    {
        "slot": 0,
        "key": "virn",
        "name_ru": "Вирн",
        "name_en": "Virn",
        "attributes": {
            "strength": 14,
            "intellect": 13,
            "dexterity": 13,
            "agility": 13,
            "vitality": 13,
            "honor": 10,
        },
        "life": 46,
        "speed_bonus": 0,
        "parry_bonus": 1,
        "playable": True,
        "summary": "Люди Предела. Ни одного провального атрибута и ни одного выдающегося; "
        "единственная раса без закрытых веток развития.",
    },
    {
        "slot": 1,
        "key": "silvar",
        "name_ru": "Сильвар",
        "name_en": "Silvar",
        "attributes": {
            "strength": 11,
            "intellect": 17,
            "dexterity": 15,
            "agility": 15,
            "vitality": 9,
            "honor": 10,
        },
        "life": 38,
        "speed_bonus": 6,
        "parry_bonus": 2,
        "playable": True,
        "summary": "Долгоживущие хранители рунного знания. Лучший разум в игре "
        "ценой худшей живучести: любая ошибка в ближнем бою смертельна.",
    },
    {
        "slot": 2,
        "key": "garn",
        "name_ru": "Гарн",
        "name_en": "Garn",
        "attributes": {
            "strength": 20,
            "intellect": 9,
            "dexterity": 10,
            "agility": 9,
            "vitality": 19,
            "honor": 10,
        },
        "life": 60,
        "speed_bonus": 0,
        "parry_bonus": 0,
        "playable": True,
        "summary": "Каменнорождённые из глубинных штолен. Ходячая крепость, "
        "которая не умеет уклоняться и почти не тянет магию.",
    },
    {
        "slot": 3,
        "key": "drakken",
        "name_ru": "Драккен",
        "name_en": "Drakken",
        "attributes": {
            "strength": 17,
            "intellect": 10,
            "dexterity": 11,
            "agility": 14,
            "vitality": 16,
            "honor": 10,
        },
        "life": 52,
        "speed_bonus": 5,
        "parry_bonus": 1,
        "playable": True,
        "summary": "Чешуйчатые кочевники солончаков. Редкое сочетание силы, "
        "живучести и подвижности; расплата — разум и точность.",
    },
    {
        "slot": 4,
        "key": "shadu",
        "name_ru": "Шаду",
        "name_en": "Shadu",
        "attributes": {
            "strength": 11,
            "intellect": 14,
            "dexterity": 16,
            "agility": 17,
            "vitality": 10,
            "honor": 10,
        },
        "life": 40,
        "speed_bonus": 10,
        "parry_bonus": 3,
        "playable": True,
        "summary": "Порождения Врат, застрявшие между мирами. Самые быстрые и "
        "скрытные; в лобовом столкновении не выживают.",
    },
]
for slot in range(5, 16):
    RACES.append(
        {
            "slot": slot,
            "key": f"reserved_{slot}",
            "name_ru": "—",
            "name_en": "Reserved",
            "attributes": {
                "strength": 10,
                "intellect": 10,
                "dexterity": 10,
                "agility": 10,
                "vitality": 10,
                "honor": 10,
            },
            "life": 40,
            "speed_bonus": 0,
            "parry_bonus": 0,
            "playable": False,
            "summary": "Слот движка, в игре не используется.",
        }
    )

# --------------------------------------------------------------------------- навыки
# Слот определяет механику внутри dlords.exe и менять его нельзя: меняются
# только название и роль в дизайне.
SKILLS: list[tuple[int, str, str, str, str, tuple[str, ...]]] = [
    (0, "brawl", "Рукопашный бой", "melee", "безоружный урон", ()),
    (1, "forms", "Боевые формы", "melee", "продвинутый безоружный бой", ("brawl",)),
    (2, "light_blade", "Лёгкие клинки", "melee", "кинжалы, короткие мечи", ()),
    (3, "medium_blade", "Средние клинки", "melee", "мечи, топоры, булавы", ()),
    (4, "heavy_arms", "Тяжёлое оружие", "melee", "двуручное оружие", ()),
    (5, "light_pole", "Лёгкое древковое", "melee", "копья, посохи", ()),
    (6, "heavy_pole", "Тяжёлое древковое", "melee", "алебарды, глефы", ()),
    (7, "dual_light", "Парные лёгкие", "melee", "два лёгких оружия", ("light_blade",)),
    (8, "dual_medium", "Парные средние", "melee", "два средних оружия", ("medium_blade",)),
    (9, "throwing", "Метательное", "ranged", "ножи, дротики, сюрикены", ()),
    (10, "archery", "Стрельба", "ranged", "луки и арбалеты", ()),
    (11, "parry", "Парирование", "defense", "шанс отбить удар", ()),
    (12, "light_armor", "Лёгкий доспех", "defense", "снимает штраф лёгкой брони", ()),
    (13, "medium_armor", "Средний доспех", "defense", "снимает штраф средней брони", ()),
    (14, "heavy_armor", "Тяжёлый доспех", "defense", "снимает штраф тяжёлой брони", ()),
    (15, "light_shield", "Лёгкий щит", "defense", "блок лёгким щитом", ()),
    (16, "medium_shield", "Средний щит", "defense", "блок средним щитом", ()),
    (17, "heavy_shield", "Тяжёлый щит", "defense", "блок тяжёлым щитом", ()),
    (18, "athletics", "Атлетика", "movement", "прыжки, перекаты, скорость", ()),
    (19, "pathfinding", "Следопытство", "movement", "обнаружение и ориентирование", ()),
    (20, "barter", "Торг", "craft", "цены у торговцев", ()),
    (21, "repair", "Починка", "craft", "восстановление прочности", ()),
    (22, "resolve", "Стойкость", "defense", "сопротивление контролю", ()),
    (23, "lockpick", "Взлом", "larceny", "замки", ("perception",)),
    (24, "perception", "Наблюдательность", "larceny", "обнаружение скрытого", ()),
    (25, "disarm", "Обезвреживание", "larceny", "ловушки", ("perception",)),
    (26, "stealth", "Скрытность", "larceny", "незаметность", ()),
    (27, "pickpocket", "Карманник", "larceny", "кража у NPC", ("stealth",)),
    (28, "identify", "Опознание", "craft", "определение свойств предметов", ()),
    (29, "shadowstrike", "Удар из тени", "melee", "атака из скрытности", ("stealth",)),
    (30, "ash_magic", "Магия Праха", "magic", "школа Праха: урон и стихии", ()),
    (31, "dawn_magic", "Магия Зари", "magic", "школа Зари: лечение и защита", ()),
    (32, "abyss_magic", "Магия Бездны", "magic", "школа Бездны: проклятия", ()),
    (33, "rune_magic", "Магия Рун", "magic", "школа Рун: врата и печати", ()),
    (34, "enchant", "Зачарование оружия", "magic", "магический урон оружием", ("light_blade",)),
    (35, "scribe", "Начертание", "craft", "запись свитков", ("ash_magic",)),
    (36, "conduit", "Проводник", "magic", "восстановление кристаллов", ("dawn_magic",)),
    (37, "alchemy", "Алхимия", "craft", "смеси и катализаторы", ("abyss_magic",)),
    (38, "rend", "Рваные раны", "passive", "кровотечение", ()),
    (39, "crush", "Сокрушение", "passive", "оглушающий удар", ()),
    (40, "precision", "Точный удар", "passive", "критический урон", ()),
    (41, "hawkeye", "Соколиный глаз", "passive", "точность дальнего боя", ()),
    (42, "spellfire", "Пламя чар", "passive", "усиление заклинаний", ()),
    (43, "bloodletting", "Кровопийство", "passive", "вампиризм", ()),
    (44, "obsidian_hand", "Обсидиановая длань", "passive", "сигнатурный навык скрытого класса", ()),
]

# --------------------------------------------------------------------------- классы
# Профиль гильдии задаёт базовый набор навыков; специализация и элита
# наследуют его и поднимают пределы. Так матрица остаётся согласованной.
GUILD_PROFILE: dict[str, dict[str, int]] = {
    "steel": {
        "medium_blade": 6,
        "heavy_arms": 5,
        "light_blade": 4,
        "parry": 5,
        "light_armor": 5,
        "medium_armor": 5,
        "heavy_armor": 4,
        "light_shield": 5,
        "medium_shield": 4,
        "athletics": 4,
        "resolve": 4,
        "repair": 3,
        "crush": 3,
        "precision": 3,
    },
    "ash": {
        "ash_magic": 6,
        "abyss_magic": 4,
        "rune_magic": 3,
        "scribe": 5,
        "enchant": 4,
        "identify": 5,
        "light_blade": 3,
        "light_armor": 3,
        "athletics": 3,
        "spellfire": 4,
        "resolve": 3,
        "alchemy": 3,
    },
    "dawn": {
        "dawn_magic": 6,
        "rune_magic": 4,
        "conduit": 5,
        "identify": 4,
        "medium_blade": 4,
        "light_pole": 3,
        "medium_armor": 4,
        "medium_shield": 4,
        "parry": 4,
        "resolve": 5,
        "athletics": 3,
        "spellfire": 3,
    },
    "dusk": {
        "light_blade": 6,
        "dual_light": 5,
        "throwing": 5,
        "archery": 4,
        "stealth": 6,
        "perception": 6,
        "lockpick": 6,
        "disarm": 5,
        "pickpocket": 5,
        "shadowstrike": 5,
        "athletics": 5,
        "light_armor": 5,
        "barter": 4,
        "precision": 4,
    },
    "storm": {
        "medium_blade": 6,
        "light_blade": 5,
        "dual_medium": 5,
        "light_pole": 5,
        "brawl": 5,
        "forms": 4,
        "parry": 6,
        "athletics": 6,
        "light_armor": 5,
        "medium_armor": 4,
        "resolve": 5,
        "precision": 4,
    },
    "sisters": {
        "light_pole": 6,
        "medium_blade": 5,
        "throwing": 4,
        "dawn_magic": 4,
        "abyss_magic": 4,
        "enchant": 5,
        "light_armor": 5,
        "medium_armor": 4,
        "parry": 5,
        "athletics": 5,
        "resolve": 5,
        "spellfire": 4,
    },
    "hidden": {
        "shadowstrike": 8,
        "stealth": 8,
        "abyss_magic": 7,
        "rune_magic": 7,
        "obsidian_hand": 10,
        "bloodletting": 7,
        "precision": 7,
        "athletics": 7,
        "light_blade": 7,
        "resolve": 7,
    },
}

# key, slot, name_ru, name_en, tier, guild, parent, требования, уровень, квест, акцент
CLASSES: list[
    tuple[str, int, str, str, str, str, str | None, dict[str, int], int, str | None, dict[str, int]]
] = [
    ("none", 0, "Нет класса", "None", "none", "", None, {}, 1, None, {}),
    # --- базовые
    ("blade", 1, "Клинок", "Blade", "base", "steel", None, {}, 1, None, {}),
    ("weaver", 2, "Ткач", "Weaver", "base", "ash", None, {}, 1, None, {}),
    ("warden", 3, "Хранитель", "Warden", "base", "dawn", None, {}, 1, None, {}),
    ("shade", 4, "Тень", "Shade", "base", "dusk", None, {}, 1, None, {}),
    # --- специалисты: Орден Стали
    (
        "bulwark",
        5,
        "Латник",
        "Bulwark",
        "specialist",
        "steel",
        "blade",
        {"strength": 25, "intellect": 20, "dexterity": 20, "vitality": 22},
        6,
        "QUEST_BULWARK",
        {"heavy_armor": 8, "heavy_shield": 8, "parry": 8, "resolve": 7, "medium_blade": 7},
    ),
    (
        "reaver",
        6,
        "Хищник",
        "Reaver",
        "specialist",
        "steel",
        "blade",
        {"strength": 25, "intellect": 15, "dexterity": 25, "agility": 20},
        6,
        "QUEST_REAVER",
        {"heavy_arms": 8, "dual_medium": 7, "rend": 7, "crush": 7, "light_armor": 7},
    ),
    # --- специалисты: Коллегия Праха
    (
        "pyromancer",
        7,
        "Пиромант",
        "Pyromancer",
        "specialist",
        "ash",
        "weaver",
        {"strength": 15, "intellect": 30, "dexterity": 25},
        6,
        "QUEST_PYROMANCER",
        {"ash_magic": 8, "spellfire": 8, "scribe": 7, "identify": 7},
    ),
    (
        "war_weaver",
        8,
        "Боевой ткач",
        "War Weaver",
        "specialist",
        "ash",
        "weaver",
        {"strength": 20, "intellect": 25, "dexterity": 25},
        6,
        "QUEST_WARWEAVER",
        {"enchant": 8, "ash_magic": 7, "medium_blade": 7, "medium_armor": 6, "parry": 6},
    ),
    # --- специалисты: Храм Зари
    (
        "lightbearer",
        9,
        "Светоносец",
        "Lightbearer",
        "specialist",
        "dawn",
        "warden",
        {"strength": 20, "intellect": 25, "dexterity": 20},
        6,
        "QUEST_LIGHTBEARER",
        {"dawn_magic": 8, "conduit": 8, "resolve": 7, "identify": 7},
    ),
    (
        "faithshield",
        10,
        "Щит Веры",
        "Faithshield",
        "specialist",
        "dawn",
        "warden",
        {"strength": 25, "intellect": 25, "dexterity": 20, "vitality": 20},
        6,
        "QUEST_FAITHSHIELD",
        {"heavy_shield": 8, "heavy_armor": 7, "dawn_magic": 7, "parry": 7, "resolve": 8},
    ),
    # --- специалисты: Сумрак
    (
        "stalker",
        11,
        "Ловчий",
        "Stalker",
        "specialist",
        "dusk",
        "shade",
        {"strength": 20, "intellect": 25, "dexterity": 25, "agility": 22},
        6,
        "QUEST_STALKER",
        {"archery": 8, "hawkeye": 8, "pathfinding": 8, "stealth": 7, "throwing": 7},
    ),
    (
        "beguiler",
        12,
        "Плут",
        "Beguiler",
        "specialist",
        "dusk",
        "shade",
        {"strength": 15, "intellect": 30, "dexterity": 25},
        6,
        "QUEST_BEGUILER",
        {"pickpocket": 8, "lockpick": 8, "disarm": 8, "barter": 8, "perception": 8},
    ),
    # --- специалисты: Дом Бури
    (
        "storm_blade",
        13,
        "Мечник Бури",
        "Storm Blade",
        "specialist",
        "storm",
        "blade",
        {"strength": 20, "intellect": 20, "dexterity": 25},
        6,
        "QUEST_STORMBLADE",
        {"medium_blade": 8, "dual_medium": 8, "parry": 8, "precision": 7},
    ),
    (
        "guardsman",
        14,
        "Гвардеец",
        "Guardsman",
        "specialist",
        "storm",
        "blade",
        {"strength": 25, "intellect": 20, "dexterity": 20},
        6,
        "QUEST_GUARDSMAN",
        {"light_pole": 8, "heavy_pole": 7, "medium_armor": 8, "medium_shield": 7, "resolve": 7},
    ),
    (
        "storm_caller",
        15,
        "Заклинатель Бури",
        "Storm Caller",
        "specialist",
        "storm",
        "weaver",
        {"strength": 15, "intellect": 25, "dexterity": 25},
        6,
        "QUEST_STORMCALLER",
        {"ash_magic": 8, "enchant": 7, "medium_blade": 6, "spellfire": 7, "athletics": 7},
    ),
    (
        "ascetic",
        16,
        "Аскет",
        "Ascetic",
        "specialist",
        "storm",
        "warden",
        {"strength": 20, "intellect": 20, "dexterity": 25},
        6,
        "QUEST_ASCETIC",
        {"brawl": 8, "forms": 8, "athletics": 8, "resolve": 8, "dawn_magic": 5},
    ),
    (
        "duelist",
        17,
        "Дуэлянт",
        "Duelist",
        "specialist",
        "storm",
        "shade",
        {"strength": 25, "intellect": 15, "dexterity": 25, "agility": 22},
        6,
        "QUEST_DUELIST",
        {"dual_light": 8, "light_blade": 8, "parry": 8, "athletics": 8, "precision": 7},
    ),
    # --- специалисты: Сёстры Пепла
    (
        "ashlance",
        18,
        "Копейщица Пепла",
        "Ashlance",
        "specialist",
        "sisters",
        "blade",
        {"strength": 25, "intellect": 25, "dexterity": 25},
        6,
        "QUEST_ASHLANCE",
        {"light_pole": 8, "heavy_pole": 8, "medium_armor": 7, "parry": 7, "enchant": 6},
    ),
    (
        "charmweaver",
        19,
        "Чаровница",
        "Charmweaver",
        "specialist",
        "sisters",
        "weaver",
        {"strength": 20, "intellect": 30, "dexterity": 20},
        6,
        "QUEST_CHARMWEAVER",
        {"abyss_magic": 8, "dawn_magic": 7, "enchant": 8, "identify": 7, "spellfire": 7},
    ),
    # --- элита: Орден Стали
    (
        "steel_lord",
        20,
        "Владыка Стали",
        "Steel Lord",
        "elite",
        "steel",
        "bulwark",
        {"strength": 40, "intellect": 30, "dexterity": 35, "vitality": 35},
        16,
        "QUEST_STEELLORD",
        {
            "heavy_armor": 10,
            "heavy_shield": 10,
            "parry": 10,
            "medium_blade": 9,
            "resolve": 9,
            "crush": 8,
        },
    ),
    (
        "bone_lord",
        21,
        "Костяной Владыка",
        "Bone Lord",
        "elite",
        "steel",
        "reaver",
        {"strength": 45, "intellect": 30, "dexterity": 35},
        16,
        "QUEST_BONELORD",
        {"heavy_arms": 10, "rend": 10, "bloodletting": 9, "abyss_magic": 7, "crush": 9},
    ),
    # --- элита: Коллегия Праха
    (
        "archweaver",
        22,
        "Архиткач",
        "Archweaver",
        "elite",
        "ash",
        "pyromancer",
        {"strength": 30, "intellect": 45, "dexterity": 40},
        16,
        "QUEST_ARCHWEAVER",
        {"ash_magic": 10, "spellfire": 10, "scribe": 9, "rune_magic": 8, "identify": 9},
    ),
    (
        "voidcaller",
        23,
        "Пожиратель Бездны",
        "Voidcaller",
        "elite",
        "ash",
        "war_weaver",
        {"strength": 35, "intellect": 40, "dexterity": 40},
        16,
        "QUEST_VOIDCALLER",
        {"abyss_magic": 10, "alchemy": 9, "enchant": 9, "bloodletting": 8, "spellfire": 9},
    ),
    # --- элита: Храм Зари
    (
        "starseer",
        24,
        "Звездочёт",
        "Starseer",
        "elite",
        "dawn",
        "lightbearer",
        {"strength": 30, "intellect": 45, "dexterity": 35},
        16,
        "QUEST_STARSEER",
        {"dawn_magic": 10, "rune_magic": 10, "conduit": 10, "identify": 9, "resolve": 9},
    ),
    (
        "chastiser",
        25,
        "Каратель",
        "Chastiser",
        "elite",
        "dawn",
        "faithshield",
        {"strength": 40, "intellect": 40, "dexterity": 35},
        16,
        "QUEST_CHASTISER",
        {"heavy_arms": 9, "heavy_armor": 10, "dawn_magic": 9, "resolve": 10, "crush": 9},
    ),
    # --- элита: Сумрак
    (
        "pathlord",
        26,
        "Владыка Троп",
        "Pathlord",
        "elite",
        "dusk",
        "stalker",
        {"strength": 35, "intellect": 40, "dexterity": 45},
        16,
        "QUEST_PATHLORD",
        {"archery": 10, "hawkeye": 10, "pathfinding": 10, "stealth": 9, "precision": 9},
    ),
    (
        "intriguer",
        27,
        "Интриган",
        "Intriguer",
        "elite",
        "dusk",
        "beguiler",
        {"strength": 30, "intellect": 45, "dexterity": 45},
        16,
        "QUEST_INTRIGUER",
        {"pickpocket": 10, "lockpick": 10, "disarm": 10, "perception": 10, "abyss_magic": 8},
    ),
    # --- элита: Дом Бури
    (
        "bannerlord",
        28,
        "Знаменосец",
        "Bannerlord",
        "elite",
        "storm",
        "guardsman",
        {"strength": 35, "intellect": 35, "dexterity": 45},
        16,
        "QUEST_BANNERLORD",
        {"heavy_pole": 10, "light_pole": 10, "medium_armor": 9, "resolve": 9, "parry": 9},
    ),
    (
        "warmaster",
        29,
        "Военачальник",
        "Warmaster",
        "elite",
        "storm",
        "storm_blade",
        {"strength": 40, "intellect": 35, "dexterity": 35},
        16,
        "QUEST_WARMASTER",
        {"medium_blade": 10, "dual_medium": 10, "crush": 9, "precision": 9, "resolve": 9},
    ),
    (
        "bladesage",
        30,
        "Мастер Клинка",
        "Bladesage",
        "elite",
        "storm",
        "storm_caller",
        {"strength": 30, "intellect": 45, "dexterity": 40},
        16,
        "QUEST_BLADESAGE",
        {"enchant": 10, "ash_magic": 9, "medium_blade": 9, "spellfire": 10, "parry": 9},
    ),
    (
        "waymaster",
        31,
        "Мастер Пути",
        "Waymaster",
        "elite",
        "storm",
        "ascetic",
        {"strength": 30, "intellect": 35, "dexterity": 45},
        16,
        "QUEST_WAYMASTER",
        {"forms": 10, "brawl": 10, "athletics": 10, "resolve": 10, "precision": 9},
    ),
    (
        "nightlord",
        32,
        "Владыка Ночи",
        "Nightlord",
        "elite",
        "storm",
        "duelist",
        {"strength": 40, "intellect": 30, "dexterity": 45},
        16,
        "QUEST_NIGHTLORD",
        {"dual_light": 10, "shadowstrike": 10, "stealth": 10, "throwing": 9, "precision": 10},
    ),
    # --- элита: Сёстры Пепла
    (
        "war_witch",
        33,
        "Ведьма Войны",
        "War Witch",
        "elite",
        "sisters",
        "charmweaver",
        {"strength": 35, "intellect": 45, "dexterity": 40},
        16,
        "QUEST_WARWITCH",
        {"abyss_magic": 10, "enchant": 10, "light_pole": 9, "spellfire": 10, "dawn_magic": 8},
    ),
    # --- скрытый класс
    (
        "obsidian_lord",
        34,
        "Владыка Обсидиана",
        "Obsidian Lord",
        "elite",
        "hidden",
        "shade",
        {"strength": 40, "intellect": 40, "dexterity": 40, "agility": 40, "vitality": 40},
        24,
        "QUEST_OBSIDIANLORD",
        {
            "obsidian_hand": 10,
            "rune_magic": 10,
            "shadowstrike": 10,
            "stealth": 10,
            "abyss_magic": 9,
        },
    ),
]

BASE_CAP = 5
TIER_UNLOCK = {"base": "base", "specialist": "specialist", "elite": "elite"}


def build_skill_access(tier: str, guild: str, accent: dict[str, int]) -> list[dict[str, Any]]:
    """Свести профиль гильдии и акцент класса в список доступов к навыкам."""
    profile = dict(GUILD_PROFILE.get(guild, {}))
    if tier == "base":
        caps = {key: min(value, BASE_CAP) for key, value in profile.items()}
    else:
        caps = dict(profile)
        for key, value in accent.items():
            caps[key] = max(caps.get(key, 0), value)
    unlock = TIER_UNLOCK.get(tier, "base")
    return [
        {"skill": key, "cap": cap, "unlock_tier": unlock if key in accent else "base"}
        for key, cap in sorted(caps.items())
    ]


def build_progression(max_level: int = 40) -> list[dict[str, int]]:
    """Кривая опыта.

    ``total_xp(L) = 75 * (L-1)^2.3``, округление до десятков. Показатель 2.3
    выбран так, чтобы уровни 1–10 проходились за первый акт, 11–24 за второй,
    а 25–40 требовали зачистки подземелий и системы Врат.
    """
    steps: list[dict[str, int]] = []
    for level in range(1, max_level + 1):
        raw = 0 if level == 1 else 75 * (level - 1) ** 2.3
        total = round(raw / 10.0) * 10
        attribute_points = 2 + (1 if level % 5 == 0 else 0)
        skill_points = 4 + (2 if level % 10 == 0 else 0)
        steps.append(
            {
                "level": level,
                "total_xp": total,
                "attribute_points": 0 if level == 1 else attribute_points,
                "skill_points": 10 if level == 1 else skill_points,
            }
        )
    return steps


def build_document() -> dict[str, Any]:
    classes: list[dict[str, Any]] = []
    for key, slot, ru, en, tier, guild, parent, req, level, quest, accent in CLASSES:
        entry: dict[str, Any] = {
            "key": key,
            "slot": slot,
            "name_ru": ru,
            "name_en": en,
            "tier": tier,
            "guild": guild,
            "parent": parent,
            "required_level": level,
            "quest_register": quest,
            "requirements": req,
            "skills": build_skill_access(tier, guild, accent),
        }
        classes.append(entry)

    return {
        "schema_version": 2,
        "title_ru": "Обсидиановые Врата",
        "title_en": "Obsidian Gate",
        "races": RACES,
        "skills": [
            {
                "slot": slot,
                "key": key,
                "name_ru": ru,
                "group": group,
                "engine_behaviour": behaviour,
                "requires": list(requires),
            }
            for slot, key, ru, group, behaviour, requires in SKILLS
        ],
        "classes": classes,
        "progression": build_progression(),
    }


def main() -> int:
    document = build_document()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )
    print(f"записано: {OUT}")
    print(
        f"расы {len(document['races'])}, навыки {len(document['skills'])}, "
        f"классы {len(document['classes'])}, уровней {len(document['progression'])}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
