"""Общий контракт кодеков.

Каждый кодек — чистая пара ``decode``/``encode`` над ``bytes``. Никакого
файлового ввода-вывода внутри: это делает кодеки тестируемыми на синтетических
данных и обеспечивает проверку round-trip без установленной игры.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class Codec(ABC, Generic[T]):
    """Двунаправленный кодек одного игрового формата."""

    #: Человекочитаемое имя формата, используется в отчётах CLI.
    name: str = "unnamed"

    #: Типичные имена файлов этого формата (для автодетекта и тестов).
    filenames: tuple[str, ...] = ()

    @abstractmethod
    def decode(self, data: bytes) -> T:
        """Разобрать ``bytes`` в модель."""

    @abstractmethod
    def encode(self, model: T) -> bytes:
        """Собрать модель обратно в ``bytes``."""

    def roundtrip_ok(self, data: bytes) -> bool:
        """Байт-в-байт ли восстанавливается вход.

        Единственный критерий, которому можно доверять при работе с закрытым
        рантаймом: если сборка не воспроизводит оригинал, писать в игру нельзя.
        """
        return self.encode(self.decode(data)) == data
