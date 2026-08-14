"""Патч характеристик предметов внутри ``dlords.exe``.

Характеристики предметов живут не в файлах данных, а в непосредственных
операндах инструкций ``MakeITEMS`` (см. :mod:`dl_toolkit.itemtab`). Изменение
значения — это правка операнда на месте: длина инструкции не меняется,
перемещений и релокаций нет, поэтому патч механический и полностью обратимый.

Ограничение, встроенное в реализацию: патчить можно только записи с
``kind == "imm"``. Значения, пришедшие через регистр (``mov [addr], bp``),
разделяются несколькими предметами, и правка регистра сломала бы соседей.
Такие поля отклоняются с внятной ошибкой, а не патчатся молча.

Порядок работы::

    plan = ItemPatch(index=..., field="price", value=5000)
    patched = apply_patches(image, [plan])          # bytes нового exe
    verify_patches(patched, [plan])                 # повторное извлечение

Проверка после применения обязательна: она заново разбирает ``MakeITEMS`` в
пропатченном образе и сверяет фактические значения с запрошенными.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from dl_toolkit.itemtab import FIELDS_BY_KEY, FieldWrite, ItemTable, extract
from dl_toolkit.pe import PeImage

_LITERAL = re.compile(r"(0x[0-9a-f]+|\d+)$")


class PatchError(RuntimeError):
    """Патч невозможно применить безопасно."""


@dataclass(frozen=True, slots=True)
class ItemPatch:
    """Запрос на изменение одного поля одного предмета."""

    index: int
    field: str
    value: int

    def __str__(self) -> str:
        return f"предмет {self.index}, поле {self.field} := {self.value}"


@dataclass(frozen=True, slots=True)
class AppliedPatch:
    """Что именно было изменено в образе."""

    patch: ItemPatch
    file_offset: int
    instruction_va: int
    width: int
    old_value: int
    new_value: int


def _locate(table: ItemTable, patch: ItemPatch) -> FieldWrite:
    spec = FIELDS_BY_KEY.get(patch.field)
    if spec is None:
        raise PatchError(f"{patch}: неизвестное поле; доступны {sorted(FIELDS_BY_KEY)}")
    if spec.key == "name":
        raise PatchError(
            f"{patch}: имя предмета патчить нельзя — оно копируется из .rdata "
            "и отображается из iname.dat, который редактируется напрямую"
        )

    candidates = table.writes_for(patch.index, spec.offset)
    if not candidates:
        raise PatchError(
            f"{patch}: поле не инициализируется в коде "
            f"(предмет {patch.index!r} = {table.name(patch.index)!r}); "
            "патчить нечего, значение остаётся нулевым"
        )
    if len(candidates) > 1:
        raise PatchError(
            f"{patch}: поле записывается {len(candidates)} раз "
            f"(VA {', '.join(hex(c.instruction_va) for c in candidates)}); "
            "требуется ручной разбор порядка записей"
        )

    write = candidates[0]
    if not write.patchable:
        raise PatchError(
            f"{patch}: значение приходит из регистра (VA 0x{write.instruction_va:08X}); "
            "регистр разделяется несколькими предметами, правка сломала бы соседей"
        )
    if not 0 <= patch.value < (1 << (8 * write.width)):
        raise PatchError(
            f"{patch}: значение не помещается в {write.width} байт "
            f"(допустимо 0..{(1 << (8 * write.width)) - 1})"
        )
    return write


def _immediate_offset(image: PeImage, write: FieldWrite) -> int:
    """Файловое смещение непосредственного операнда внутри инструкции."""
    try:
        from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("для патча нужен пакет capstone") from exc

    start = image.to_offset(write.instruction_va)
    if start is None:
        raise PatchError(f"инструкция 0x{write.instruction_va:08X} вне образа")

    disassembler = Cs(CS_ARCH_X86, CS_MODE_32)
    instruction = next(
        iter(disassembler.disasm(image.data[start : start + 16], write.instruction_va))
    )

    match = _LITERAL.search(instruction.op_str)
    if match is None or int(match.group(1), 0) != write.value:
        raise PatchError(
            f"инструкция 0x{write.instruction_va:08X} ({instruction.mnemonic} "
            f"{instruction.op_str}) не содержит ожидаемого операнда {write.value}"
        )

    encoded = write.value.to_bytes(write.width, "little")
    body = image.data[start : start + instruction.size]
    position = body.rfind(encoded)
    if position < 0 or position + write.width != instruction.size:
        raise PatchError(
            f"не удалось однозначно найти операнд в инструкции 0x{write.instruction_va:08X}"
        )
    return start + position


def plan_patches(image: PeImage, patches: list[ItemPatch]) -> list[AppliedPatch]:
    """Проверить патчи и вычислить смещения, ничего не записывая."""
    table = extract(image)
    planned: list[AppliedPatch] = []
    used: set[int] = set()
    for patch in patches:
        write = _locate(table, patch)
        offset = _immediate_offset(image, write)
        if offset in used:
            raise PatchError(f"{patch}: та же инструкция уже патчится другим запросом")
        used.add(offset)
        planned.append(
            AppliedPatch(
                patch=patch,
                file_offset=offset,
                instruction_va=write.instruction_va,
                width=write.width,
                old_value=write.value,
                new_value=patch.value,
            )
        )
    return planned


def apply_patches(image: PeImage, patches: list[ItemPatch]) -> tuple[bytes, list[AppliedPatch]]:
    """Применить патчи и вернуть новый образ вместе с отчётом."""
    planned = plan_patches(image, patches)
    data = bytearray(image.data)
    for entry in planned:
        data[entry.file_offset : entry.file_offset + entry.width] = entry.new_value.to_bytes(
            entry.width, "little"
        )
    return bytes(data), planned


def verify_patches(patched: bytes, patches: list[ItemPatch]) -> list[str]:
    """Заново разобрать пропатченный образ и вернуть список расхождений."""
    table = extract(PeImage.parse(patched))
    problems: list[str] = []
    for patch in patches:
        actual = table.value(patch.index, patch.field)
        if actual != patch.value:
            problems.append(f"{patch}: в образе {actual}, ожидалось {patch.value}")
    return problems
