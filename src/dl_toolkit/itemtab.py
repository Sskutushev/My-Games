"""Таблица предметов, вкомпилированная в ``dlords.exe``.

**`D6ITEM.DAT` движком не читается.** В образе нет ни строки ``D6ITEM``, ни
``ITEM.DAT``. Настоящая таблица строится функцией ``MakeITEMS()``
(VA ``0x004ED670``, ~116 КБ кода, 19 984 инструкции), которая заполняет
статический массив ``0x030DF40C`` непосредственными записями::

    mov  ecx, dword ptr [0x0065BA6C]   ; "CHAIN MITTENS" из .rdata
    mov  dword ptr [0x030DF5A4], ecx   ; имя записи 2
    mov  word  ptr [0x030DF5CC], 0x68  ; иконка записи 3
    mov  bp, 1                          ; часть значений идёт через регистры
    mov  word  ptr [0x030DF4F8], bp

Значения пишутся и напрямую, и через регистры, поэтому восстановление требует
пропагации констант по линейному коду функции. Без неё теряется около 60 %
полей.

Раскладка массива, полученная разбором:

============  =========================================================
База          ``0x030DF40C``
Шаг записи    204 байта
Записей       948 (индексы 0…947)
Соответствие  ``iname.dat`` id = индекс + 1
============  =========================================================

Соответствие проверено строго: из 510 записей, где имя задано в коде, **510
совпали** с ``iname.dat[idx + 1]``. Соседние сдвиги дают 13–16 совпадений, то
есть случайный шум.

Оставшиеся 438 записей код не трогает вообще — они остаются нулевыми. Это
алхимические реагенты и рунные камни (``BAT WING``, ``RAT TAIL``, ``AENIR``…),
которым характеристики не нужны. Второго инициализатора в образе нет: сканирование
всей секции ``.text`` находит обращения к массиву только внутри ``MakeITEMS`` и
в 99 мелких местах, читающих отдельные предметы в рантайме.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import IntEnum

from dl_toolkit.pe import PeImage

ITEM_ARRAY_BASE = 0x030DF40C
ITEM_STRIDE = 204
ITEM_COUNT = 948
MAKEITEMS_VA = 0x004ED670
NAME_SIZE = 32

_REG32 = frozenset({"eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"})
_SUBREG = {
    "ax": "eax", "bx": "ebx", "cx": "ecx", "dx": "edx",
    "si": "esi", "di": "edi", "bp": "ebp",
    "al": "eax", "bl": "ebx", "cl": "ecx", "dl": "edx",
    "ah": "eax", "bh": "ebx", "ch": "ecx", "dh": "edx",
}  # fmt: skip
_WIDTH = {"byte": 1, "word": 2, "dword": 4}
_ABSOLUTE = re.compile(r"\[(0x[0-9a-f]+)\]$")
_LITERAL = re.compile(r"^(0x[0-9a-f]+|\d+)$")
#: Инструкции, после которых значение регистра-приёмника перестаёт быть известным.
_CLOBBER = frozenset(
    {"or", "and", "add", "sub", "lea", "imul", "shl", "shr", "inc", "dec", "movsx", "movzx"}
)


class ItemType(IntEnum):
    """Значения поля ``+32``. Выведены группировкой 510 именованных записей."""

    UNTYPED = 0
    WEAPON = 1
    AMMO = 3
    ARMOR = 4
    SHIELD = 5
    SPECIAL = 6
    POTION = 8
    GOLD = 14
    DOCUMENT = 15
    ACCESSORY = 17
    LOCKPICK = 20


class EquipSlot(IntEnum):
    """Значения поля ``+34`` для брони."""

    TORSO = 0
    LEGS = 1
    HANDS = 3
    FEET = 4
    HEAD = 5
    HAIR = 6
    SHOULDERS = 7
    RIGHT_SHOULDER = 8
    LEFT_SHOULDER = 9


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """Описание поля записи предмета."""

    offset: int
    width: int
    key: str
    title: str
    confidence: str
    note: str = ""


#: Семантика полей. ``confidence``: ``high`` — подтверждено группировкой и
#: перекрёстной проверкой, ``medium`` — согласуется с примерами, ``low`` — гипотеза.
FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec(0, NAME_SIZE, "name", "внутреннее имя", "high", "ASCII, совпадает с iname.dat"),
    FieldSpec(32, 2, "type", "тип предмета", "high", "см. ItemType"),
    FieldSpec(34, 2, "slot", "слот экипировки", "high", "см. EquipSlot; для оружия — иное"),
    FieldSpec(36, 2, "weapon_class", "класс оружия", "medium", "1 одноручное, 2 двуручное"),
    FieldSpec(40, 2, "icon", "иконка", "high", "индекс в interface/icons"),
    FieldSpec(42, 2, "icon_alt", "вторая иконка", "medium", "встречается у украшений"),
    FieldSpec(44, 2, "model", "модель", "high", "индекс модели GR2"),
    FieldSpec(46, 2, "model_flag", "флаг модели", "low"),
    FieldSpec(58, 2, "armor", "защита", "medium", "у брони и щитов"),
    FieldSpec(60, 4, "price", "цена", "high", "1…500000, медиана 2500 у оружия"),
    FieldSpec(68, 2, "hands", "занимаемые руки", "medium", "2 у двуручного"),
    FieldSpec(72, 2, "skill", "требуемый навык", "high", "id навыка 1800+N"),
    FieldSpec(78, 4, "reach", "дальность", "medium", "фикс. точка /1024: 1280=1.25, 2560=2.5"),
    FieldSpec(96, 2, "field_96", "неизвестно", "low"),
    FieldSpec(106, 2, "field_106", "неизвестно", "low"),
    FieldSpec(108, 2, "field_108", "неизвестно", "low"),
    FieldSpec(110, 2, "damage", "урон", "medium", "меч 12–18, двуручник 36, лук 10"),
    FieldSpec(118, 2, "tier", "класс качества", "low", "1…3"),
)

FIELDS_BY_KEY: dict[str, FieldSpec] = {spec.key: spec for spec in FIELDS}


@dataclass(frozen=True, slots=True)
class FieldWrite:
    """Одна запись в поле предмета, найденная в коде."""

    item_index: int
    field_offset: int
    width: int
    value: int
    instruction_va: int
    #: ``imm`` — значение в операнде инструкции (патчится); ``reg`` — пришло из регистра.
    kind: str

    @property
    def patchable(self) -> bool:
        """Можно ли изменить значение, не меняя длину инструкции."""
        return self.kind == "imm"


@dataclass(slots=True)
class ItemTable:
    """Реконструированная таблица предметов."""

    memory: bytearray = field(default_factory=lambda: bytearray(ITEM_COUNT * ITEM_STRIDE))
    writes: list[FieldWrite] = field(default_factory=list)
    instructions: int = 0
    unresolved: int = 0

    # ------------------------------------------------------------------ чтение
    def raw(self, index: int) -> bytes:
        self._check(index)
        return bytes(self.memory[index * ITEM_STRIDE : (index + 1) * ITEM_STRIDE])

    def name(self, index: int) -> str:
        chunk = self.raw(index)[:NAME_SIZE]
        end = chunk.find(b"\x00")
        return chunk[: end if end >= 0 else NAME_SIZE].decode("cp1251", "replace")

    def value(self, index: int, key_or_offset: str | int) -> int:
        """Значение поля по ключу из :data:`FIELDS` или по числовому смещению."""
        spec = self._spec(key_or_offset)
        base = index * ITEM_STRIDE + spec.offset
        self._check(index)
        return int.from_bytes(self.memory[base : base + spec.width], "little")

    def defined_indices(self) -> list[int]:
        """Записи, у которых задано имя — то есть реально описанные предметы."""
        return [i for i in range(ITEM_COUNT) if self.name(i)]

    def writes_for(self, index: int, offset: int) -> list[FieldWrite]:
        return [w for w in self.writes if w.item_index == index and w.field_offset == offset]

    def as_dict(self, index: int) -> dict[str, int | str]:
        row: dict[str, int | str] = {
            "index": index,
            "iname_id": index + 1,
            "name": self.name(index),
        }
        for spec in FIELDS:
            if spec.key != "name":
                row[spec.key] = self.value(index, spec.key)
        return row

    # ------------------------------------------------------------------ служебное
    @staticmethod
    def _check(index: int) -> None:
        if not 0 <= index < ITEM_COUNT:
            raise IndexError(f"индекс предмета {index} вне 0..{ITEM_COUNT - 1}")

    @staticmethod
    def _spec(key_or_offset: str | int) -> FieldSpec:
        if isinstance(key_or_offset, str):
            spec = FIELDS_BY_KEY.get(key_or_offset)
            if spec is None:
                raise KeyError(f"неизвестное поле {key_or_offset!r}")
            return spec
        for spec in FIELDS:
            if spec.offset == key_or_offset:
                return spec
        return FieldSpec(key_or_offset, 2, f"field_{key_or_offset}", "неизвестно", "low")


def _register(operand: str) -> str | None:
    name = operand.strip()
    if name in _REG32:
        return name
    return _SUBREG.get(name)


def _absolute(operand: str) -> tuple[int, int] | None:
    match = _ABSOLUTE.search(operand)
    if not match:
        return None
    width = _WIDTH.get(operand.split()[0], 4)
    return int(match.group(1), 16), width


def extract(image: PeImage, *, max_instructions: int = 40_000) -> ItemTable:
    """Разобрать ``MakeITEMS`` и восстановить таблицу предметов.

    Выполняется линейный проход с пропагацией констант: функция не содержит
    ветвлений внутрь, поэтому прохода до первого ``ret`` достаточно.
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
    registers: dict[str, int] = {}

    for instruction in disassembler.disasm(image.data[start : start + 400_000], MAKEITEMS_VA):
        table.instructions += 1
        if table.instructions > max_instructions or instruction.mnemonic == "ret":
            break

        mnemonic = instruction.mnemonic
        destination, _, source = instruction.op_str.partition(", ")

        if mnemonic == "xor" and destination == source:
            register = _register(destination)
            if register:
                registers[register] = 0
            continue

        if mnemonic in _CLOBBER:
            register = _register(destination)
            if register:
                registers.pop(register, None)
            continue

        if mnemonic != "mov":
            continue

        register = _register(destination)
        if register is not None:
            if _LITERAL.match(source):
                registers[register] = int(source, 0)
                continue
            loaded = _absolute(source)
            if loaded is None:
                registers.pop(register, None)
                continue
            offset = image.to_offset(loaded[0])
            if offset is None:
                registers.pop(register, None)
            else:
                registers[register] = int.from_bytes(
                    image.data[offset : offset + loaded[1]], "little"
                )
            continue

        target = _absolute(destination)
        if target is None:
            continue
        address, width = target
        if not ITEM_ARRAY_BASE <= address < limit:
            continue

        if _LITERAL.match(source):
            value, kind = int(source, 0), "imm"
        else:
            source_register = _register(source)
            if source_register is None or source_register not in registers:
                table.unresolved += 1
                continue
            value, kind = registers[source_register] & ((1 << (8 * width)) - 1), "reg"

        relative = address - ITEM_ARRAY_BASE
        table.memory[relative : relative + width] = value.to_bytes(width, "little")
        table.writes.append(
            FieldWrite(
                item_index=relative // ITEM_STRIDE,
                field_offset=relative % ITEM_STRIDE,
                width=width,
                value=value,
                instruction_va=instruction.address,
                kind=kind,
            )
        )

    return table
