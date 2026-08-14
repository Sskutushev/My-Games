"""Лут- и торговые списки (``D6TRLIST.DAT``).

Формат::

    223 записи по 60 байт
    запись 0        — маркер (uint32 = 222)
    байты 0..23     — ASCII-имя списка
    байты 24..59    — 18 * uint16, id предметов из ``iname.dat``

Ноль означает пустой слот. Это самая свободная таблица в игре: занято 1514 из
3996 слотов, поэтому именно здесь балансировать добычу дешевле всего.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dl_toolkit.binio import BinaryFormatError, Reader, Writer
from dl_toolkit.codecs.base import Codec

RECORD_SIZE = 60
NAME_SIZE = 24
ENTRY_COUNT = 18


@dataclass(slots=True)
class LootList:
    """Именованный список предметов."""

    index: int
    name_raw: bytes
    entries: list[int] = field(default_factory=list)

    @property
    def name(self) -> str:
        end = self.name_raw.find(b"\x00")
        return self.name_raw[: end if end >= 0 else len(self.name_raw)].decode("cp1251", "replace")

    @name.setter
    def name(self, value: str) -> None:
        raw = value.encode("cp1251", "replace")
        if len(raw) >= NAME_SIZE:
            raise BinaryFormatError(f"имя списка {value!r} длиннее {NAME_SIZE - 1} Б")
        self.name_raw = raw + b"\x00" * (NAME_SIZE - len(raw))

    @property
    def used(self) -> int:
        return sum(1 for e in self.entries if e)

    @property
    def free(self) -> int:
        return ENTRY_COUNT - self.used

    def item_ids(self) -> list[int]:
        """Только заполненные слоты."""
        return [e for e in self.entries if e]

    def add(self, item_id: int) -> None:
        """Положить предмет в первый свободный слот."""
        for i, value in enumerate(self.entries):
            if not value:
                self.entries[i] = item_id
                return
        raise BinaryFormatError(
            f"список {self.index} ({self.name!r}) заполнен: все 18 слотов заняты"
        )


@dataclass(slots=True)
class LootTable:
    marker: bytes
    lists: list[LootList] = field(default_factory=list)

    def by_name(self, name: str) -> LootList:
        for entry in self.lists:
            if entry.name == name:
                return entry
        raise KeyError(f"списка {name!r} нет в таблице")

    def by_index(self, index: int) -> LootList:
        for entry in self.lists:
            if entry.index == index:
                return entry
        raise KeyError(f"списка {index} нет в таблице")

    def free_capacity(self) -> int:
        """Сколько всего свободных слотов под предметы во всей таблице."""
        return sum(entry.free for entry in self.lists)

    def empty_lists(self) -> list[int]:
        return [entry.index for entry in self.lists if entry.used == 0]


class LootListCodec(Codec[LootTable]):
    name = "trlist"
    filenames = ("D6TRLIST.DAT",)

    def decode(self, data: bytes) -> LootTable:
        if len(data) % RECORD_SIZE:
            raise BinaryFormatError(f"размер {len(data)} не кратен {RECORD_SIZE}")
        reader = Reader(data)
        table = LootTable(marker=reader.raw(RECORD_SIZE))
        for index in range(1, len(data) // RECORD_SIZE):
            reader.seek(index * RECORD_SIZE)
            table.lists.append(
                LootList(
                    index=index,
                    name_raw=reader.raw(NAME_SIZE),
                    entries=reader.u16_array(ENTRY_COUNT),
                )
            )
        return table

    def encode(self, model: LootTable) -> bytes:
        writer = Writer().raw(model.marker)
        for entry in sorted(model.lists, key=lambda e: e.index):
            if len(entry.name_raw) != NAME_SIZE:
                raise BinaryFormatError(f"имя списка {entry.index} неверной длины")
            if len(entry.entries) != ENTRY_COUNT:
                raise BinaryFormatError(
                    f"список {entry.index}: {len(entry.entries)} слотов вместо {ENTRY_COUNT}"
                )
            writer.raw(entry.name_raw).u16_array(entry.entries)
        return writer.data()
