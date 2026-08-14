"""Таблица предметов, вкомпилированная в ``dlords.exe``.

Открытие, меняющее всю картину моддинга: **`D6ITEM.DAT` движком не читается.**
В образе нет ни строки ``D6ITEM.DAT``, ни какой-либо строки с ``ITEM.DAT``.
Настоящая таблица предметов строится функцией ``MakeITEMS()``
(VA ``0x004ED670``, ~116 КБ кода, около 20 000 инструкций), которая инициализирует
статический массив по адресу ``0x030DF40C`` серией непосредственных записей::

    mov  dword ptr [0x030DF48A], 2          ; поле записи 0
    mov  word  ptr [0x030DF4F8], bp         ; поле записи 1
    mov  ecx,  dword ptr [0x0065BA6C]       ; "CHAIN MITTENS" из .rdata
    mov  dword ptr [0x030DF5A4], ecx        ; имя записи 2

Параметры массива, полученные разбором функции:

* база ``0x030DF40C``, шаг записи **204** байта, записей **948** (индексы 0..947);
* индекс записи в exe соответствует ``iname.dat`` как ``iname_id = index + 1``
  (проверено: PUNCH → 1, BAT BITE → 2, CHAIN MITTENS → 3, CHAIN BOOTS → 4).

Практические следствия:

* редактирование ``D6ITEM.DAT`` не влияет ни на что;
* переименование предметов работает через ``iname.dat`` без патча exe;
* изменение характеристик требует правки непосредственных операндов внутри
  ``MakeITEMS``. Длина инструкции при этом не меняется, перемещений нет —
  патч механический и обратимый.

Модуль извлекает таблицу из образа и раскладывает по индексам предметов.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from dl_toolkit.pe import PeImage

#: Адрес и раскладка статического массива предметов.
ITEM_ARRAY_BASE = 0x030DF40C
ITEM_STRIDE = 204
ITEM_COUNT = 948
MAKEITEMS_VA = 0x004ED670

_ABS_OPERAND = re.compile(r"\[(0x[0-9a-f]+)\]")
_IMM_OPERAND = re.compile(r",\s*(0x[0-9a-f]+|\d+)$")

_WIDTH_BY_PREFIX = {"byte": 1, "word": 2, "dword": 4, "qword": 8}


@dataclass(frozen=True, slots=True)
class FieldWrite:
    """Одна непосредственная запись в поле предмета."""

    address: int
    item_index: int
    field_offset: int
    width: int
    value: int | None
    instruction_va: int
    source_string: str | None = None


@dataclass(slots=True)
class ItemTable:
    """Реконструированная таблица предметов."""

    writes: list[FieldWrite] = field(default_factory=list)

    def indices(self) -> list[int]:
        return sorted({write.item_index for write in self.writes})

    def by_item(self, index: int) -> list[FieldWrite]:
        return sorted(
            (w for w in self.writes if w.item_index == index), key=lambda w: w.field_offset
        )

    def field_usage(self) -> dict[int, int]:
        """Сколько предметов трогает каждое смещение поля — подсказка о семантике."""
        usage: dict[int, int] = {}
        for write in self.writes:
            usage[write.field_offset] = usage.get(write.field_offset, 0) + 1
        return dict(sorted(usage.items()))

    def strings_for(self, index: int) -> list[str]:
        return [w.source_string for w in self.by_item(index) if w.source_string]


def _decode_target(operand: str) -> tuple[int, int] | None:
    """Из операнда вида ``dword ptr [0x30df48a]`` вернуть (адрес, ширина)."""
    match = _ABS_OPERAND.search(operand)
    if not match:
        return None
    address = int(match.group(1), 16)
    width = 4
    for prefix, size in _WIDTH_BY_PREFIX.items():
        if operand.startswith(prefix):
            width = size
            break
    return address, width


def extract(image: PeImage, *, max_instructions: int = 40_000) -> ItemTable:
    """Разобрать ``MakeITEMS`` и собрать все записи в массив предметов.

    Требует ``capstone``. Функция линейная, без ветвлений внутрь, поэтому
    линейного прохода до первого ``ret`` достаточно.
    """
    try:
        from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    except ImportError as exc:  # pragma: no cover - зависит от окружения
        raise RuntimeError("для разбора MakeITEMS нужен пакет capstone") from exc

    start = image.to_offset(MAKEITEMS_VA)
    if start is None:
        raise ValueError(f"адрес MakeITEMS 0x{MAKEITEMS_VA:08X} вне образа")

    disassembler = Cs(CS_ARCH_X86, CS_MODE_32)
    table = ItemTable()
    limit = ITEM_ARRAY_BASE + ITEM_COUNT * ITEM_STRIDE
    pending_string: str | None = None
    count = 0

    for instruction in disassembler.disasm(image.data[start : start + 400_000], MAKEITEMS_VA):
        count += 1
        if count > max_instructions or instruction.mnemonic == "ret":
            break
        if instruction.mnemonic != "mov":
            continue

        destination, _, source = instruction.op_str.partition(", ")

        # Загрузка константной строки из .rdata: запоминаем до следующей записи.
        if not destination.startswith(("byte", "word", "dword", "qword")):
            loaded = _decode_target(source)
            if loaded:
                pending_string = image.read_cstring(loaded[0])
            continue

        target = _decode_target(destination)
        if target is None:
            continue
        address, width = target
        if not ITEM_ARRAY_BASE <= address < limit:
            pending_string = None
            continue

        relative = address - ITEM_ARRAY_BASE
        immediate = _IMM_OPERAND.search(instruction.op_str)
        value = int(immediate.group(1), 0) if immediate else None

        table.writes.append(
            FieldWrite(
                address=address,
                item_index=relative // ITEM_STRIDE,
                field_offset=relative % ITEM_STRIDE,
                width=width,
                value=value,
                instruction_va=instruction.address,
                source_string=pending_string,
            )
        )
        pending_string = None

    return table
