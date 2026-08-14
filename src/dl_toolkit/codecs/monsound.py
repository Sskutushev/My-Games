"""Реестр звуковых эффектов (``MONSOUND.DAT``).

Это не двоичный файл, а комментированный текстовый конфиг::

    742             * MAXIMUM # OF SOUND RECORDS
    11,"spell_fireball.wav",22050,R,   * DLORDS FIREBALL SFX_FIREBALL 11
    -1,""                              * END OF SOUNDS

``*`` начинает комментарий, ``R`` помечает резидентный (предзагружаемый) звук,
``-1`` завершает таблицу. Самая дешёвая точка модификации во всей игре.

Кодек сохраняет исходные строки целиком, поэтому запись файла без правок
воспроизводит его байт-в-байт вместе с комментариями и отступами.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from dl_toolkit.codecs.base import Codec

_ENTRY_RE = re.compile(
    r"""^(?P<indent>\s*)
        (?P<id>-?\d+)\s*,\s*
        "(?P<wav>[^"]*)"\s*
        (?:,\s*(?P<rate>\d+))?\s*
        (?P<rest>.*)$""",
    re.VERBOSE,
)


@dataclass(slots=True)
class SoundEntry:
    """Разобранная строка реестра."""

    line_no: int
    sfx_id: int
    wav: str
    sample_rate: int | None
    resident: bool
    comment: str


@dataclass(slots=True)
class SoundRegistry:
    """Реестр целиком: исходные строки плюс разбор.

    ``raw_lines`` — источник истины для записи; ``entries`` — представление для
    анализа и правки.
    """

    raw_lines: list[str] = field(default_factory=list)
    line_ending: str = "\r\n"
    trailing_newline: bool = True
    entries: list[SoundEntry] = field(default_factory=list)

    @property
    def max_records(self) -> int:
        """Объявленный в шапке лимит слотов."""
        for line in self.raw_lines:
            match = re.match(r"^\s*(\d+)\s+\*\s*MAXIMUM", line)
            if match:
                return int(match.group(1))
        return 0

    def by_id(self, sfx_id: int) -> SoundEntry:
        for entry in self.entries:
            if entry.sfx_id == sfx_id:
                return entry
        raise KeyError(f"звука {sfx_id} нет в реестре")

    def free_ids(self) -> list[int]:
        used = {e.sfx_id for e in self.entries if e.sfx_id >= 0}
        return [i for i in range(self.max_records) if i not in used]

    def set_wav(self, sfx_id: int, wav: str) -> None:
        """Заменить файл у существующего слота, сохранив частоту и комментарий."""
        entry = self.by_id(sfx_id)
        line = self.raw_lines[entry.line_no]
        self.raw_lines[entry.line_no] = re.sub(r'"[^"]*"', f'"{wav}"', line, count=1)
        entry.wav = wav


class MonSoundCodec(Codec[SoundRegistry]):
    name = "monsound"
    filenames = ("MONSOUND.DAT",)

    def decode(self, data: bytes) -> SoundRegistry:
        text = data.decode("cp1251", "replace")
        line_ending = "\r\n" if "\r\n" in text else "\n"
        trailing = text.endswith(line_ending)
        body = text[: -len(line_ending)] if trailing else text
        raw_lines = body.split(line_ending)

        registry = SoundRegistry(
            raw_lines=raw_lines, line_ending=line_ending, trailing_newline=trailing
        )
        for line_no, line in enumerate(raw_lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("*"):
                continue
            match = _ENTRY_RE.match(line)
            if not match:
                continue
            rest = match.group("rest")
            comment = rest.split("*", 1)[1].strip() if "*" in rest else ""
            flags = rest.split("*", 1)[0]
            registry.entries.append(
                SoundEntry(
                    line_no=line_no,
                    sfx_id=int(match.group("id")),
                    wav=match.group("wav"),
                    sample_rate=int(match.group("rate")) if match.group("rate") else None,
                    resident="R" in flags,
                    comment=comment,
                )
            )
        return registry

    def encode(self, model: SoundRegistry) -> bytes:
        text = model.line_ending.join(model.raw_lines)
        if model.trailing_newline:
            text += model.line_ending
        return text.encode("cp1251", "replace")
