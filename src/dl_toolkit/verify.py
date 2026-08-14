"""Проверка round-trip по установленной игре.

Единственная объективная гарантия корректности кодека при закрытом рантайме:
если ``encode(decode(x)) != x``, писать этим кодеком в игру нельзя.
"""

from __future__ import annotations

from dataclasses import dataclass

from dl_toolkit.codecs import CodeFileCodec, LootListCodec, MonSoundCodec, StringTableCodec
from dl_toolkit.codecs.base import Codec
from dl_toolkit.game import GameRoot
from dl_toolkit.schema import FIXED_TABLES, STRING_TABLES


@dataclass(slots=True)
class VerifyResult:
    """Итог проверки одного файла."""

    file: str
    codec: str
    ok: bool
    size: int
    detail: str = ""

    @property
    def status(self) -> str:
        return "OK" if self.ok else "FAIL"


def _check(root: GameRoot, relative: str, codec: Codec[object]) -> VerifyResult:
    try:
        data = root.read(relative)
    except FileNotFoundError as exc:
        return VerifyResult(relative, codec.name, False, 0, f"нет файла: {exc}")
    try:
        rebuilt = codec.encode(codec.decode(data))
    except Exception as exc:
        return VerifyResult(relative, codec.name, False, len(data), f"{type(exc).__name__}: {exc}")
    if rebuilt == data:
        return VerifyResult(relative, codec.name, True, len(data))
    return VerifyResult(
        relative,
        codec.name,
        False,
        len(data),
        f"расхождение: получено {len(rebuilt)} Б, ожидалось {len(data)} Б",
    )


def verify_all(root: GameRoot, *, script_limit: int | None = None) -> list[VerifyResult]:
    """Прогнать round-trip по всем поддерживаемым файлам установки."""
    results: list[VerifyResult] = []

    string_codec: Codec[object] = StringTableCodec()  # type: ignore[assignment]
    for filename in STRING_TABLES:
        results.append(_check(root, filename, string_codec))

    for spec in FIXED_TABLES:
        results.append(_check(root, spec.filename, spec.codec()))  # type: ignore[arg-type]

    results.append(_check(root, "D6TRLIST.DAT", LootListCodec()))  # type: ignore[arg-type]
    results.append(_check(root, "MONSOUND.DAT", MonSoundCodec()))  # type: ignore[arg-type]

    script_codec = CodeFileCodec()
    scripts = root.glob("npccode/CODEFILE.*")
    if script_limit is not None:
        scripts = scripts[:script_limit]
    for script in scripts:
        relative = f"npccode/{script.name}"
        results.append(_check(root, relative, script_codec))  # type: ignore[arg-type]

    return results


def summarize(results: list[VerifyResult]) -> tuple[int, int]:
    """Вернуть ``(успешно, всего)``."""
    return sum(1 for r in results if r.ok), len(results)
