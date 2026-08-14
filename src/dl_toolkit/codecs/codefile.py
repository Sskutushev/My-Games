"""Скрипты NPC, диалогов и квестов (``npccode/CODEFILE.NNN``).

Формат контейнера::

    повторяется до конца файла:
        uint32 tag      — адрес строки, цель переходов goto
        uint32 length   — длина блока с текстом
        char[length]    — NUL-терминированный текст оператора (CP1251)

``tag`` — не порядковый номер: он растёт неравномерно и служит адресом для
``goto $LABEL``. Наблюдаемое правило — накопительная «стоимость» операторов:
объявления (``if``/``endif``/метки) стоят 0, исполняемые операторы — от 1 и
выше. Точная функция стоимости не выведена, поэтому кодек **сохраняет исходные
теги** и пересчитывает их только по явному запросу.

Это осознанный компромисс: правка текста существующего оператора безопасна
всегда, а вставка и удаление операторов требуют либо проверенной модели тегов,
либо ручной простановки.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dl_toolkit.binio import BinaryFormatError, Reader, Writer
from dl_toolkit.codecs.base import Codec


@dataclass(slots=True)
class ScriptLine:
    """Один оператор скрипта."""

    tag: int
    text: str
    #: Байты после ``NUL`` внутри блока. В оригиналах встречаются, сохраняются
    #: ради байт-в-байт round-trip.
    trailing: bytes = b""

    @property
    def statement(self) -> str:
        """Текст без ведущих табуляций и завершающей точки-терминатора."""
        return self.text.strip().rstrip(".")

    @property
    def is_label(self) -> bool:
        return self.statement.startswith("$")

    @property
    def keyword(self) -> str:
        """Первое слово оператора в нижнем регистре, пусто для меток и пустых строк."""
        stripped = self.text.strip()
        if not stripped or stripped.startswith("$"):
            return ""
        head = stripped.split()[0]
        return head.split("(")[0].lower()


@dataclass(slots=True)
class ScriptFile:
    """Разобранный ``CODEFILE`` целиком."""

    lines: list[ScriptLine] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.lines)

    def statements(self) -> list[str]:
        return [line.text for line in self.lines]

    def find(self, needle: str) -> list[int]:
        """Индексы строк, содержащих подстроку."""
        return [i for i, line in enumerate(self.lines) if needle in line.text]

    def labels(self) -> dict[str, int]:
        """``$МЕТКА -> tag``. Цели переходов ``goto``."""
        out: dict[str, int] = {}
        for line in self.lines:
            stripped = line.text.strip()
            if stripped.startswith("$"):
                out[stripped.split()[0].rstrip(".")] = line.tag
        return out

    def replace_text(self, index: int, text: str) -> None:
        """Заменить текст оператора, не трогая тег.

        Безопасная операция: длина блока в контейнере не фиксирована, а тег
        сохраняется, поэтому все ``goto`` остаются валидными.
        """
        if not 0 <= index < len(self.lines):
            raise IndexError(f"строки {index} нет в скрипте")
        self.lines[index].text = text
        self.lines[index].trailing = b""


class CodeFileCodec(Codec[ScriptFile]):
    name = "codefile"
    filenames = ("CODEFILE.001",)

    def decode(self, data: bytes) -> ScriptFile:
        reader = Reader(data)
        script = ScriptFile()
        while reader.remaining >= 8:
            tag = reader.u32()
            length = reader.u32()
            if length <= 0 or reader.remaining < length:
                raise BinaryFormatError(
                    f"блок длиной {length} по смещению {reader.pos} выходит за файл"
                )
            block = reader.raw(length)
            end = block.find(b"\x00")
            if end < 0:
                raise BinaryFormatError(f"блок по смещению {reader.pos - length} без NUL")
            script.lines.append(
                ScriptLine(
                    tag=tag,
                    text=block[:end].decode("cp1251", "replace"),
                    trailing=block[end + 1 :],
                )
            )
        if reader.remaining:
            raise BinaryFormatError(f"хвост {reader.remaining} Б не разобран")
        return script

    def encode(self, model: ScriptFile) -> bytes:
        writer = Writer()
        for line in model.lines:
            block = line.text.encode("cp1251", "replace") + b"\x00" + line.trailing
            writer.u32(line.tag).u32(len(block)).raw(block)
        return writer.data()
