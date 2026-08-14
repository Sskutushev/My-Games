"""Схемы известных таблиц игры и их измеренные параметры.

Значения ниже получены измерением установленной сборки Dungeon Lords v1.5, а не
догадками. ``free_slots`` — записи с пустым именем, единственные безопасные
кандидаты на переиспользование до тех пор, пока не доказано, что счётчик в
записи-маркере можно поднимать.
"""

from __future__ import annotations

from dataclasses import dataclass

from dl_toolkit.codecs.fixedtab import FixedTableCodec


@dataclass(frozen=True, slots=True)
class TableSpec:
    """Описание одной таблицы фиксированных записей."""

    filename: str
    record_size: int
    name_size: int
    kind_size: int
    expected_records: int
    description: str

    def codec(self) -> FixedTableCodec:
        return FixedTableCodec(self.record_size, self.name_size, self.kind_size)


FIXED_TABLES: tuple[TableSpec, ...] = (
    TableSpec("D6ITEM.DAT", 284, 22, 22, 858, "предметы, экипировка и описания атак"),
    TableSpec("D6MONS.DAT", 340, 22, 0, 819, "боевые архетипы монстров и NPC"),
    TableSpec("D6NPC.DAT", 36, 24, 0, 160, "NPC; индекс совпадает с npccode/CODEFILE.NNN"),
    TableSpec("D6PROP.DAT", 64, 22, 0, 560, "архетипы интерактивных объектов мира"),
    TableSpec("D6MONSND.DAT", 184, 28, 0, 120, "наборы звуков монстров"),
)

STRING_TABLES: tuple[str, ...] = (
    "rd6string.dat",
    "iname.dat",
    "mname.dat",
    "pname.dat",
)

#: Диапазоны id в ``rd6string.dat``. Верхняя граница файла — 9905, занято 2128,
#: то есть свободно около 7778 id под новый контент.
STRING_RANGES: dict[str, tuple[int, int]] = {
    "attributes": (1100, 1105),
    "races": (1300, 1315),
    "classes": (1400, 1434),
    "creature_categories": (1600, 1615),
    "skills": (1800, 1844),
    "status_effects": (2200, 2215),
    "area_transitions": (3500, 3599),
    "strike_effects": (4650, 4712),
    "combat_effects": (4750, 4765),
    "item_slots": (4800, 4999),
    "inventory_ui": (5000, 5599),
    "network_ui": (5600, 5999),
    "character_creation": (7000, 7999),
}

#: Группы региональных файлов: 64 слота каждая, заполнена меньшая часть.
REGION_GROUPS: dict[str, str] = {
    "TRIG": "триггеры",
    "TRAP": "ловушки",
    "SWIT": "переключатели и состояния",
    "BOUN": "границы и переходы",
    "SPEC": "специальная логика региона",
    "LINK": "связи (в оригинале не используются)",
}

REGION_SLOTS = 64
