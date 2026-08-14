"""Таблицы фиксированных записей DEEP6 (семейство ``D6*.DAT``).

Общий каркас всех таблиц движка::

    запись 0        — маркер: первый uint32 = число используемых записей
    записи 1..N     — данные
    байты 0..K      — внутреннее ASCII-имя
    далее           — числовые поля uint16 little-endian

Кодек намеренно не интерпретирует числовые поля: семантика большинства смещений
не доказана, а сохранение сырого хвоста гарантирует байт-в-байт round-trip.
Известные поля описываются отдельно, в :mod:`dl_toolkit.schema`.

Поля имени хранятся сырыми байтами. В оригинальных файлах после ``NUL`` внутри
поля имени встречается мусор от предыдущего содержимого; если декодировать в
``str`` и добивать нулями, round-trip разойдётся. Сырое хранение делает запись
байт-в-байт точной, а перекодировка происходит только при фактическом
редактировании имени.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from dl_toolkit.binio import ENCODING, BinaryFormatError, Reader, Writer
from dl_toolkit.codecs.base import Codec


def _decode_field(raw: bytes) -> str:
    end = raw.find(b"\x00")
    return raw[: end if end >= 0 else len(raw)].decode(ENCODING, "replace")


def _encode_field(text: str, size: int) -> bytes:
    raw = text.encode(ENCODING, "replace")
    if len(raw) >= size:
        raise BinaryFormatError(
            f"строка {text!r} не помещается в {size} Б (нужно {len(raw)} + NUL)"
        )
    return raw + b"\x00" * (size - len(raw))


@dataclass(slots=True)
class FixedRecord:
    """Одна запись таблицы: сырые поля имени/вида и сырой числовой хвост."""

    index: int
    name_raw: bytes
    kind_raw: bytes
    tail: bytes

    @property
    def name(self) -> str:
        return _decode_field(self.name_raw)

    @name.setter
    def name(self, value: str) -> None:
        self.name_raw = _encode_field(value, len(self.name_raw))

    @property
    def kind(self) -> str:
        return _decode_field(self.kind_raw)

    @kind.setter
    def kind(self, value: str) -> None:
        if not self.kind_raw:
            raise BinaryFormatError("в этой таблице нет поля вида")
        self.kind_raw = _encode_field(value, len(self.kind_raw))

    @property
    def _numeric_base(self) -> int:
        return len(self.name_raw) + len(self.kind_raw)

    def u16(self, offset: int) -> int:
        """Прочитать ``uint16`` по смещению от начала записи."""
        rel = offset - self._numeric_base
        if rel < 0 or rel + 2 > len(self.tail):
            raise BinaryFormatError(f"смещение {offset} вне числовой части записи {self.index}")
        return int(struct.unpack_from("<H", self.tail, rel)[0])

    def set_u16(self, offset: int, value: int) -> None:
        rel = offset - self._numeric_base
        if rel < 0 or rel + 2 > len(self.tail):
            raise BinaryFormatError(f"смещение {offset} вне числовой части записи {self.index}")
        buf = bytearray(self.tail)
        struct.pack_into("<H", buf, rel, value & 0xFFFF)
        self.tail = bytes(buf)


@dataclass(slots=True)
class FixedTable:
    """Таблица фиксированных записей вместе с сырой записью-маркером."""

    record_size: int
    name_size: int
    kind_size: int
    marker: bytes
    records: list[FixedRecord] = field(default_factory=list)

    @property
    def declared_count(self) -> int:
        """Значение счётчика из записи-маркера."""
        return int(struct.unpack_from("<I", self.marker, 0)[0])

    @declared_count.setter
    def declared_count(self, value: int) -> None:
        buf = bytearray(self.marker)
        struct.pack_into("<I", buf, 0, value)
        self.marker = bytes(buf)

    def __len__(self) -> int:
        return len(self.records)

    def by_index(self, index: int) -> FixedRecord:
        for record in self.records:
            if record.index == index:
                return record
        raise KeyError(f"записи {index} нет в таблице")

    def free_slots(self) -> list[int]:
        """Записи с пустым именем — единственные безопасные кандидаты на переиспользование."""
        return [r.index for r in self.records if not r.name.strip()]

    def u16_column(self, offset: int) -> list[tuple[int, int]]:
        """Значение одного числового поля по всем записям — для поиска семантики полей."""
        return [(r.index, r.u16(offset)) for r in self.records]


class FixedTableCodec(Codec[FixedTable]):
    """Параметризуемый кодек: размер записи и раскладка имён задаются схемой."""

    name = "fixedtab"

    def __init__(self, record_size: int, name_size: int, kind_size: int = 0) -> None:
        if record_size <= 0:
            raise ValueError("record_size должен быть положительным")
        if name_size + kind_size > record_size:
            raise ValueError("имя и метка вида не помещаются в запись")
        self.record_size = record_size
        self.name_size = name_size
        self.kind_size = kind_size

    def decode(self, data: bytes) -> FixedTable:
        if len(data) % self.record_size:
            raise BinaryFormatError(
                f"размер {len(data)} не кратен размеру записи {self.record_size}"
            )
        total = len(data) // self.record_size
        if total < 1:
            raise BinaryFormatError("таблица пуста: нет даже записи-маркера")

        reader = Reader(data)
        table = FixedTable(
            record_size=self.record_size,
            name_size=self.name_size,
            kind_size=self.kind_size,
            marker=reader.raw(self.record_size),
        )
        tail_size = self.record_size - self.name_size - self.kind_size
        for index in range(1, total):
            reader.seek(index * self.record_size)
            table.records.append(
                FixedRecord(
                    index=index,
                    name_raw=reader.raw(self.name_size),
                    kind_raw=reader.raw(self.kind_size),
                    tail=reader.raw(tail_size),
                )
            )
        return table

    def encode(self, model: FixedTable) -> bytes:
        if len(model.marker) != self.record_size:
            raise BinaryFormatError("длина записи-маркера не равна размеру записи")
        writer = Writer().raw(model.marker)
        tail_size = self.record_size - self.name_size - self.kind_size
        for record in sorted(model.records, key=lambda r: r.index):
            if len(record.name_raw) != self.name_size:
                raise BinaryFormatError(f"поле имени записи {record.index} неверной длины")
            if len(record.kind_raw) != self.kind_size:
                raise BinaryFormatError(f"поле вида записи {record.index} неверной длины")
            if len(record.tail) != tail_size:
                raise BinaryFormatError(
                    f"хвост записи {record.index}: {len(record.tail)} Б вместо {tail_size}"
                )
            writer.raw(record.name_raw).raw(record.kind_raw).raw(record.tail)
        return writer.data()
