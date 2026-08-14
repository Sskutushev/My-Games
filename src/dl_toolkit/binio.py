"""Низкоуровневый двоичный ввод-вывод.

Слой ничего не знает об игре: только чтение и запись примитивов в little-endian
и строк в CP1251. Все игровые кодеки строятся поверх него.
"""

from __future__ import annotations

import struct
from typing import Final

ENCODING: Final = "cp1251"


class BinaryFormatError(ValueError):
    """Данные не соответствуют ожидаемой структуре формата."""


class Reader:
    """Курсорное чтение из ``bytes``."""

    __slots__ = ("buf", "pos")

    def __init__(self, buf: bytes, pos: int = 0) -> None:
        self.buf = buf
        self.pos = pos

    def __len__(self) -> int:
        return len(self.buf)

    @property
    def remaining(self) -> int:
        return len(self.buf) - self.pos

    def seek(self, pos: int) -> Reader:
        if pos < 0 or pos > len(self.buf):
            raise BinaryFormatError(f"seek за пределы буфера: {pos} (размер {len(self.buf)})")
        self.pos = pos
        return self

    def _unpack(self, fmt: str, size: int) -> int:
        if self.pos + size > len(self.buf):
            raise BinaryFormatError(
                f"чтение {size} Б по смещению {self.pos} выходит за буфер {len(self.buf)}"
            )
        value: int = struct.unpack_from(fmt, self.buf, self.pos)[0]
        self.pos += size
        return value

    def u8(self) -> int:
        return self._unpack("<B", 1)

    def u16(self) -> int:
        return self._unpack("<H", 2)

    def i16(self) -> int:
        return self._unpack("<h", 2)

    def u32(self) -> int:
        return self._unpack("<I", 4)

    def i32(self) -> int:
        return self._unpack("<i", 4)

    def f32(self) -> float:
        if self.pos + 4 > len(self.buf):
            raise BinaryFormatError(f"чтение f32 по смещению {self.pos} выходит за буфер")
        value: float = struct.unpack_from("<f", self.buf, self.pos)[0]
        self.pos += 4
        return value

    def raw(self, count: int) -> bytes:
        if self.pos + count > len(self.buf):
            raise BinaryFormatError(
                f"чтение {count} Б по смещению {self.pos} выходит за буфер {len(self.buf)}"
            )
        chunk = self.buf[self.pos : self.pos + count]
        self.pos += count
        return chunk

    def u16_array(self, count: int) -> list[int]:
        return [self.u16() for _ in range(count)]

    def i16_array(self, count: int) -> list[int]:
        return [self.i16() for _ in range(count)]

    def u32_array(self, count: int) -> list[int]:
        return [self.u32() for _ in range(count)]

    def fixed_str(self, size: int) -> str:
        """Строка фиксированной длины, обрезанная по первому ``NUL``."""
        chunk = self.raw(size)
        end = chunk.find(b"\x00")
        return chunk[: end if end >= 0 else size].decode(ENCODING, "replace")

    def cstr(self) -> str:
        """``NUL``-терминированная строка от текущей позиции."""
        end = self.buf.find(b"\x00", self.pos)
        if end < 0:
            raise BinaryFormatError(f"нет NUL-терминатора после смещения {self.pos}")
        text = self.buf[self.pos : end].decode(ENCODING, "replace")
        self.pos = end + 1
        return text

    def cstr_at(self, offset: int) -> str:
        """``NUL``-терминированная строка по абсолютному смещению; курсор не двигается."""
        if offset < 0 or offset >= len(self.buf):
            raise BinaryFormatError(f"смещение строки {offset} вне буфера {len(self.buf)}")
        end = self.buf.find(b"\x00", offset)
        if end < 0:
            end = len(self.buf)
        return self.buf[offset:end].decode(ENCODING, "replace")


class Writer:
    """Накопительная запись в ``bytearray``."""

    __slots__ = ("out",)

    def __init__(self) -> None:
        self.out = bytearray()

    def __len__(self) -> int:
        return len(self.out)

    def u8(self, value: int) -> Writer:
        self.out += struct.pack("<B", value & 0xFF)
        return self

    def u16(self, value: int) -> Writer:
        self.out += struct.pack("<H", value & 0xFFFF)
        return self

    def i16(self, value: int) -> Writer:
        self.out += struct.pack("<h", value)
        return self

    def u32(self, value: int) -> Writer:
        self.out += struct.pack("<I", value & 0xFFFFFFFF)
        return self

    def i32(self, value: int) -> Writer:
        self.out += struct.pack("<i", value)
        return self

    def f32(self, value: float) -> Writer:
        self.out += struct.pack("<f", value)
        return self

    def raw(self, data: bytes) -> Writer:
        self.out += data
        return self

    def u16_array(self, values: list[int]) -> Writer:
        self.out += struct.pack(f"<{len(values)}H", *[v & 0xFFFF for v in values])
        return self

    def i16_array(self, values: list[int]) -> Writer:
        self.out += struct.pack(f"<{len(values)}h", *values)
        return self

    def u32_array(self, values: list[int]) -> Writer:
        self.out += struct.pack(f"<{len(values)}I", *[v & 0xFFFFFFFF for v in values])
        return self

    def fixed_str(self, text: str, size: int) -> Writer:
        """Строка фиксированной длины с ``NUL``-добивкой.

        Переполнение — ошибка, а не молчаливая обрезка: молчаливая обрезка в
        игровых таблицах приводит к порче соседних полей.
        """
        raw = text.encode(ENCODING, "replace")
        if len(raw) >= size:
            raise BinaryFormatError(
                f"строка {text!r} не помещается в {size} Б (нужно {len(raw)} + NUL)"
            )
        self.out += raw + b"\x00" * (size - len(raw))
        return self

    def cstr(self, text: str) -> Writer:
        self.out += text.encode(ENCODING, "replace") + b"\x00"
        return self

    def pad_to(self, offset: int, fill: int = 0) -> Writer:
        if len(self.out) > offset:
            raise BinaryFormatError(
                f"данные ({len(self.out)} Б) уже длиннее целевого смещения {offset}"
            )
        self.out += bytes([fill]) * (offset - len(self.out))
        return self

    def data(self) -> bytes:
        return bytes(self.out)
