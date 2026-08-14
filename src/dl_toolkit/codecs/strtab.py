"""Индексированные строковые таблицы DEEP6.

Формат (``rd6string.dat``, ``iname.dat``, ``mname.dat``, ``pname.dat``)::

    uint32 count
    count * { uint32 id; uint32 offset }
    блок NUL-терминированных строк в CP1251

Смещения абсолютны от начала файла.

Оригинальные файлы **не** дедуплицируют одинаковые строки: каждая запись
получает собственное место в куче. Проверено round-trip на всех четырёх
таблицах установленной сборки — дедупликация даёт файл на 4–16 % короче
оригинала и ломает байт-в-байт совпадение. Поэтому по умолчанию кодировщик
пишет строки подряд в порядке записей; ``intern=True`` доступен как опция для
сжатия собственных файлов, но для записи в игру использовать его не следует.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dl_toolkit.binio import BinaryFormatError, Reader, Writer
from dl_toolkit.codecs.base import Codec


@dataclass(slots=True)
class StringTable:
    """Упорядоченная таблица ``id -> строка``.

    Порядок записей сохраняется: в файле id не обязаны идти по возрастанию, а
    движок, вероятно, полагается на позиционный индекс.
    """

    entries: list[tuple[int, str]] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.entries)

    def as_dict(self) -> dict[int, str]:
        return dict(self.entries)

    def get(self, string_id: int, default: str = "") -> str:
        for sid, text in self.entries:
            if sid == string_id:
                return text
        return default

    def set(self, string_id: int, text: str) -> None:
        """Заменить существующую строку или добавить новую в конец."""
        for index, (sid, _) in enumerate(self.entries):
            if sid == string_id:
                self.entries[index] = (string_id, text)
                return
        self.entries.append((string_id, text))

    def free_ids(self, low: int, high: int) -> list[int]:
        """Незанятые id в диапазоне ``[low, high]`` — куда можно класть новый контент."""
        used = {sid for sid, _ in self.entries}
        return [i for i in range(low, high + 1) if i not in used]


class StringTableCodec(Codec[StringTable]):
    name = "strtab"
    filenames = ("rd6string.dat", "iname.dat", "mname.dat", "pname.dat")

    def __init__(self, *, intern: bool = False) -> None:
        #: Дедуплицировать одинаковые строки. Оригинальные файлы этого не делают.
        self.intern = intern

    def decode(self, data: bytes) -> StringTable:
        reader = Reader(data)
        count = reader.u32()
        if count > (len(data) - 4) // 8:
            raise BinaryFormatError(f"count={count} не помещается в файл размером {len(data)}")
        index: list[tuple[int, int]] = [(reader.u32(), reader.u32()) for _ in range(count)]
        return StringTable([(sid, reader.cstr_at(offset)) for sid, offset in index])

    def encode(self, model: StringTable) -> bytes:
        header = Writer()
        header.u32(len(model.entries))
        heap_base = 4 + len(model.entries) * 8

        heap = Writer()
        interned: dict[str, int] = {}
        offsets: list[int] = []
        for _, text in model.entries:
            offset = interned.get(text) if self.intern else None
            if offset is None:
                offset = heap_base + len(heap)
                interned[text] = offset
                heap.cstr(text)
            offsets.append(offset)

        for (sid, _), offset in zip(model.entries, offsets):
            header.u32(sid).u32(offset)
        return header.data() + heap.data()
