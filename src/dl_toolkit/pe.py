"""Минимальный разбор PE-образа.

Нужен ровно для одного: перевода между файловыми смещениями и виртуальными
адресами ``dlords.exe``. Полноценный парсер PE тут избыточен.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from dl_toolkit.binio import BinaryFormatError


@dataclass(frozen=True, slots=True)
class Section:
    name: str
    virtual_address: int
    virtual_size: int
    raw_pointer: int
    raw_size: int


@dataclass(frozen=True, slots=True)
class PeImage:
    """Загруженный PE-образ с таблицей секций."""

    data: bytes
    image_base: int
    sections: tuple[Section, ...]

    @classmethod
    def parse(cls, data: bytes) -> PeImage:
        if data[:2] != b"MZ":
            raise BinaryFormatError("не MZ-образ")
        pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
        if data[pe_offset : pe_offset + 4] != b"PE\0\0":
            raise BinaryFormatError("не найдена сигнатура PE")

        coff = pe_offset + 4
        section_count = struct.unpack_from("<H", data, coff + 2)[0]
        optional_size = struct.unpack_from("<H", data, coff + 16)[0]
        optional = coff + 20
        image_base = struct.unpack_from("<I", data, optional + 28)[0]

        sections = []
        table = optional + optional_size
        for index in range(section_count):
            entry = table + index * 40
            name = data[entry : entry + 8].rstrip(b"\0").decode("ascii", "replace")
            virtual_size, virtual_address, raw_size, raw_pointer = struct.unpack_from(
                "<IIII", data, entry + 8
            )
            sections.append(Section(name, virtual_address, virtual_size, raw_pointer, raw_size))
        return cls(data, image_base, tuple(sections))

    def to_offset(self, virtual_address: int) -> int | None:
        """Виртуальный адрес → файловое смещение; ``None`` для неинициализированных данных."""
        for section in self.sections:
            low = self.image_base + section.virtual_address
            if low <= virtual_address < low + section.virtual_size:
                offset = section.raw_pointer + (virtual_address - low)
                return offset if offset < len(self.data) else None
        return None

    def to_virtual(self, offset: int) -> int | None:
        for section in self.sections:
            if section.raw_pointer <= offset < section.raw_pointer + section.raw_size:
                return self.image_base + section.virtual_address + (offset - section.raw_pointer)
        return None

    def read_cstring(self, virtual_address: int, limit: int = 128) -> str | None:
        """ASCII-строка по виртуальному адресу, если там действительно строка."""
        offset = self.to_offset(virtual_address)
        if offset is None:
            return None
        chunk = self.data[offset : offset + limit]
        end = chunk.find(b"\x00")
        if end <= 1:
            return None
        text = chunk[:end]
        if not all(32 <= byte < 127 for byte in text):
            return None
        return text.decode("ascii")
