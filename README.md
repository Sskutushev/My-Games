# My-Games

Реверс-инжиниринг движка **DEEP6** (Dungeon Lords, Heuristic Park, 2004) и тотальная
конверсия на его основе — **«Обсидиановые Врата» / Obsidian Gate**.

[![CI](https://github.com/Sskutushev/My-Games/actions/workflows/ci.yml/badge.svg)](https://github.com/Sskutushev/My-Games/actions/workflows/ci.yml)

---

## Что здесь

| Каталог | Содержимое |
|---|---|
| `src/dl_toolkit/` | Пакет `dl-toolkit`: кодеки игровых форматов, модель дизайна, CLI |
| `tests/` | Тесты, включая round-trip по настоящей установке игры |
| `tools/` | Генераторы данных дизайна |
| `data/obsidian_gate/` | Свод правил новой игры (генерируемый артефакт) |
| `docs/` | Технический разбор движка и дизайн-документ |
| `.github/workflows/` | CI: линт, формат, типы, миграции, тесты, сборка |

Файлы самой игры (2.88 ГБ ассетов) в репозиторий **не входят**. Путь к установке
задаётся переменной `DL_GAME_ROOT`.

---

## Главный результат

Все поддерживаемые форматы читаются и записываются **байт-в-байт**: 169 файлов
установки Dungeon Lords v1.5, включая все 158 скриптов NPC.

```
$ DL_GAME_ROOT="C:/Games/Dungeon Lords" dl verify
round-trip: 169/169
```

Это предусловие любой модификации: при закрытом рантайме единственная объективная
проверка кодека — совпадение `encode(decode(x)) == x`.

---

## Быстрый старт

```bash
python -m pip install -e ".[dev]"
export DL_GAME_ROOT="/path/to/Dungeon Lords"   # Windows: $env:DL_GAME_ROOT=...

dl verify                                  # round-trip всех форматов
dl capacity                                # свободная ёмкость таблиц
dl rules data/obsidian_gate/ruleset.yaml   # валидация свода правил
dl rules data/obsidian_gate/ruleset.yaml --matrix
dl migrate data/obsidian_gate/ruleset.yaml --write
dl restore D6TRLIST.DAT                    # откат файла из резервной копии
```

Регенерация свода правил после правки правил дизайна:

```bash
python tools/generate_ruleset.py
```

---

## Архитектура

Слои строго снизу вверх, зависимости только вниз:

```
binio        примитивы двоичного ввода-вывода, ничего не знают об игре
  ↓
codecs       чистые пары decode/encode на каждый формат, без файлового I/O
  ↓
schema       измеренные параметры таблиц конкретной сборки
  ↓
game         доступ к установке: резервные копии, атомарная запись, манифест
  ↓
verify       round-trip как предусловие записи
  ↓
content      предметная модель новой игры поверх ограничений движка
  ↓
cli          пользовательский интерфейс
```

Кодеки не открывают файлы: это делает их тестируемыми на синтетических данных и
позволяет прогонять round-trip без установленной игры. Подробнее — в
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Поддерживаемые форматы

| Формат | Файлы | Статус |
|---|---|---|
| Строковые таблицы | `rd6string.dat`, `iname.dat`, `mname.dat`, `pname.dat` | round-trip ✅ |
| Таблицы фиксированных записей | `D6ITEM`, `D6MONS`, `D6NPC`, `D6PROP`, `D6MONSND` | round-trip ✅ |
| Лут- и торговые списки | `D6TRLIST.DAT` | round-trip ✅ |
| Скрипты NPC и квестов | `npccode/CODEFILE.*` (158 шт.) | round-trip ✅ |
| Реестр звуков | `MONSOUND.DAT` | round-trip ✅ |
| Декларации событий | `EVENTS.DCL` | разобран, кодек в работе |
| Байткод событий | `EVENTS.COD` | точки входа известны, опкоды нет |
| Геометрия и ландшафт | `.bsp`, `.twd`, `TERRDATA.*` | закрыты |
| Контейнер `SFFS` | `speech.dat`, `root.dat`, `compass.dat` | закрыт |

---

## Документация

- [`docs/DEEP6_ENGINE_REPORT.md`](docs/DEEP6_ENGINE_REPORT.md) — полный технический разбор движка
- [`docs/ENGINE_LIMITS.md`](docs/ENGINE_LIMITS.md) — **разбор кода загрузчиков: какие таблицы расширяемы**
- [`docs/ITEM_TABLE.md`](docs/ITEM_TABLE.md) — **таблица предметов внутри exe: раскладка, семантика полей, патч**
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — архитектура тулкита и принципы
- [`docs/DATA_ARCHITECTURE.md`](docs/DATA_ARCHITECTURE.md) — современный стек и слоёные БД: что уместно, что нет
- [`docs/OBSIDIAN_GATE_GDD.md`](docs/OBSIDIAN_GATE_GDD.md) — дизайн-документ новой игры
- [`docs/CONTENT_BUDGET.md`](docs/CONTENT_BUDGET.md) — измеренная ёмкость таблиц

### Главное открытие

`D6ITEM.DAT` движком **не читается**: в `dlords.exe` нет такой строки. Настоящая
таблица предметов вкомпилирована в функцию `MakeITEMS()` — 948 записей по 204
байта в статическом массиве `0x030DF40C`, заполняемых 20 000 инструкций.
Индекс записи соответствует `iname.dat` как `iname_id = index + 1`: проверено на
510 записях, 510 совпадений, ноль расхождений.

Это закрывает противоречие, которое числилось нерешённым во всех предыдущих
отчётах: моста между `iname.dat` и `D6ITEM.DAT` нет, потому что `D6ITEM.DAT` —
не таблица предметов, а данные более ранней версии движка.

Характеристики предметов извлекаются и патчатся:

```bash
dl items --csv items.csv --find katana   # 510 предметов с полями
dl items-patch plan.yaml --write         # правка операндов в exe, откат через dl restore
```

---

## Разработка

```bash
ruff format .          # форматирование
ruff check .           # линт
mypy                   # строгая типизация
pytest                 # тесты
pytest -m "not gamedata"   # без тестов на реальной игре
```

CI прогоняет всё перечисленное на Python 3.11 и 3.12, плюс проверку миграций и
сборку пакета. Порог покрытия — 90 %.

---

## Лицензия

MIT — на код тулкита. Ассеты и данные игры Dungeon Lords принадлежат
правообладателям и в репозитории не распространяются.
