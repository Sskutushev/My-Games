# Dungeon Lords Collector's Edition v1.5 — полный технический разбор

Дата: 2026-08-14
Объект: `C:\Games\Dungeon Lords`
Метод: статический реверс-инжиниринг установленной сборки. Игра не запускалась.
Предыдущие отчёты: `documentation/legacy_reports/` (сохранены как есть, часть выводов ниже их исправляет).

---

## 0. Что изменилось по сравнению с прошлыми отчётами

Пять утверждений прошлых отчётов оказались неверными или неполными:

| Прошлый вывод | Факт |
|---|---|
| «Квестовая логика закрыта в бинарном байткоде, править нельзя» | Квесты и диалоги лежат в `npccode/CODEFILE.NNN` — **читаемый текстовый скрипт**, 158 файлов, 1.5 МБ, полный английский текст реплик внутри |
| «`npccode/` требует отдельного декодирования» | Формат тривиальный: `[u32 tag][u32 len][текст]`. Все 158 файлов распарсились без ошибок |
| «`EVENTS.DCL` содержит метки, нужен декодер» | `EVENTS.DCL` — полная таблица символов: 182 примитива событий, **с текстовыми описаниями на английском** и словарём параметров |
| «Связь NPC ↔ данные неизвестна» | `CODEFILE.NNN` = запись `NNN` в `D6NPC.DAT`. Проверено: NPC 1 = Staroxia, скрипт 001 содержит `qa "I am Staroxia, Seer of the Stars…"` |
| «Регионов ~30» | Слотов регионов 64 (`D6*00..63`), заполнена меньшая часть; остальные — 4-байтовые заглушки с `count=0` |

Дополнительно найдено то, чего в прошлых отчётах не было вообще: движок называется **DEEP6**, в сборке **включены читы**, `MONSOUND.DAT` — текстовый редактируемый реестр звуков, есть `DEBUG.LOG` с полной трассой инициализации движка.

---

## 1. Идентификация продукта

| Параметр | Значение |
|---|---|
| Игра | Dungeon Lords Collector's Edition |
| Версия | 1.5 |
| Разработчик | Heuristic Park (D.W. Bradley) |
| Локализация | 1С / Nival Interactive, русская, CP1251 |
| Год | 2004–2005 |
| Внутреннее имя движка | **DEEP6** (отсюда префикс `D6` у всех таблиц данных) |
| Исполняемый файл | `dlords.exe`, 2 715 648 байт, native Win32 |
| API рендера | Direct3D 9 (fallback DirectDraw software canvas) |
| Требования (из `readme.txt`) | Win98/Me/2000/XP, DX 9.0c, 384 МБ RAM, 2.8 ГБ HDD, GPU с T&L (GeForce2 GTS+) |
| Мультиплеер | 2–8 игроков, TCP/IP + GameSpy, **UDP порт 2606** |
| Ключ запуска | `dlords -gdi` — оконный/GDI-режим (из readme) |

Установка: **10 791 файл, 2.88 ГБ**.

Крупнейшие потребители места:

| Расширение | Файлов | МБ | Что это |
|---|---:|---:|---|
| `.dat` | 405 | 1040 | почти весь объём — `speech.dat` (1.01 ГБ) |
| `.GR2` | 4964 | 538 | модели и анимации Granny 3D |
| `.bmp` | 3380 | 385 | текстуры, UI, иконки |
| `.twd` | 40 | 325 | world/terrain-данные уровней |
| `.bik` | 6 | 162 | видеоролики Bink |
| `.TEX` | 1 | 105 | `TERRDATA.TEX`, глобальный атлас текстур ландшафта |
| `.bsp` | 40 | 95 | геометрия уровней |
| `.wav` | 661 | 53 | звуковые эффекты |

---

## 2. Архитектура рантайма

### 2.1. Сторонние библиотеки

| Библиотека | Файл | Роль |
|---|---|---|
| Granny 3D (RAD) | `granny2.dll` | скелетная анимация, меши `.GR2` |
| Bink Video (RAD) | `binkw32.dll` | `.bik` ролики |
| Miles Sound System (RAD) | `mss32.dll` + `MilesRD/*.asi`, `*.m3d`, `*.flt` | микшер, 3D-звук, кодеки |
| DirectX 9 | системная | D3D9 рендер, DirectInput, DirectDraw |

Своего в движке: файловая система данных, BSP/terrain-рендер, скриптовая VM событий, интерпретатор NPC-скриптов, боевая и RPG-логика.

### 2.2. Порядок инициализации (восстановлен из `DEBUG.LOG`)

`DEBUG.LOG` — не мусор, а полная трасса реального запуска. Из неё видна вся структура движка:

```
WinMain
 └ CC_CheckForD3D → CC_Create_Direct3D → CC_Enum_Direct3DDevices
 └ ConfigGamma_Load → CreateWindow
 └ InitSystem
     ├ D6ClearAlloc          менеджер памяти
     ├ TrigTables            предрасчёт тригонометрии
     ├ DI_Init / DI_InitKeyboard / DI_InitMouse
     ├ InitBindings          загрузка .kbd
     ├ ConLex_Process        лексер консольных команд
     └ Screen_Open → Card_Init_DD_D3D → Card_Software_Compliant
 └ PlayTheGame
     └ InitStuff
         ├ LoadPaths         SSPATH.DAT
         ├ InitSpells        таблицы заклинаний
         ├ InitSFXQ          очередь звуковых эффектов
         ├ InitCAM_ZBUF      камера/Z-буфер
         ├ LoadFONTS         *.FNT
         ├ LoadSTRINGS       rd6string.dat, iname/mname/pname
         ├ LoadPointers      курсоры interface/*.ptr
         ├ LoadTLISTS        D6TRLIST.DAT (лут-листы)
         ├ LoadResidentGFX   BUTTONS / TEXTWIN / INTERFACE
         ├ LoadCONFIG        gameopt.dat
         ├ MakeITEMS         D6ITEM.DAT
         ├ InitPCDisplay / InitPlayers / InitInterps
         ├ InitGRN           Granny runtime
         ├ InitSPELL_EXT / _EFXLIST / _EFX / _PARTICLE / _EMITTERS / _PROPEFX
         ├ LoadSOUNDS        MONSOUND.DAT + sounds/
         ├ LoadGMDATA        игровые данные
         ├ SetWorldTime      игровые сутки
         ├ InitBSPCACHE / InitLIGHTFADE
         └ CDROMMediaCheck   проверка носителя
 └ LOAD SEGMENT: N
     INITSKYANDTREE → INITLISTS → INITMONSTERS → INITEFX → INITNPC
     → INITMISSILE → INITEVQUEUES → TERRAIN → TERRAINMESH → NAVPOINTS
     → BSP LOAD → SEGREAD (D6SEGnn.GAM) → CONTROLLER OBJECTS → OBJECTS → BSPSFX
```

Практические выводы из трассы:

- **Мир поделён на «сегменты»** (`LOAD SEGMENT: 0`). Сегмент — крупный кусок мира с собственным terrain, BSP-набором, монстрами, NPC и объектами. `D6SEG00.NFO` — метаданные сегмента 0.
- **Сохранение состояния сегмента** пишется в `D6SEGnn.GAM` (в этой установке отсутствуют → мир в исходном состоянии, сейвов нет).
- Есть механика **«Return to Town»** (`RETURN TO TOWN: PLOC_TOWN`) — принудительный возврат партии в город.
- Есть **партия**: `gPartyN=1`, `group_party`, `split_party`. Одиночная игра — это партия из одного персонажа.
- Модели монстров грузятся/выгружаются по индексам (`UNLOAD GRANNY MODEL [26]`) — индекс соответствует записи в `D6MONS.DAT`.
- В логе видна реальная ошибка данных: `GRANNY MODEL ERROR MESHCOUNT==0 (torchpoleA.grn)` — сломанная модель факельного столба, воспроизводится трижды.

### 2.3. Консоль и биндинги

Движок имеет консольный слой команд (`ConLex_Process`, `InitBindings`). Конфиги — обычный текст:

| Файл | Роль |
|---|---|
| `autoexec.kbd` | автозапуск; **сейчас содержит `exec cheats.kbd`** |
| `default.kbd` | базовые биндинги |
| `CHEATS.KBD` | читерские команды |

**Читы в этой сборке включены** (`autoexec.kbd` безусловно подгружает `cheats.kbd`):

| Клавиша | Команда | Действие |
|---|---|---|
| `F9` | `debug` | режим отладки |
| `g` | `genenc` | принудительная генерация энкаунтера |
| `t` | `mon_freeze` | заморозка монстров |
| `y` | `fly` | полёт |

Закомментированы, но доступны: `remote_cyc`, `remote_off`, `mon_passive`, `weather`, `+d_modelmip`, `pc_kill`.

Команды движка из `default.kbd` — часть из них не описана в мануале: `realtime_turnbase` (переключение real-time / пошагового боя), `group_party`, `split_party`, `cam_swinglock`, `cam_toggle`, `cam_move`, `+cam_swingright/left`, `attack_mode`, `mouse_menu`, `devstats`, `+safemode_override`, `+viewdistin/out`, `centerview`, `run_toggle`, `hotkey_talk`.

Полный список: `documentation/extracted/console_bindings.csv` (55 записей).

> Важно: `default.kbd` — это дефолты **движка DEEP6**, а не финальная раскладка Dungeon Lords. Финальные биндинги (E=inventory, C=character, L=journal и т.д.) переопределяются внутри `dlords.exe`. Расхождение мануала и `default.kbd` — не ошибка мануала.

---

## 3. Полный справочник форматов данных

### 3.1. Сводная таблица

| Файл | Размер | Записей | Байт/запись | Статус | Содержимое |
|---|---:|---:|---:|---|---|
| `rd6string.dat` | 59 713 | 2128 | var | ✅ decoded | UI/интерфейсные строки, RU |
| `iname.dat` | 21 592 | 948 | var | ✅ decoded | имена предметов и заклинаний |
| `mname.dat` | 9 327 | 435 | var | ✅ decoded | имена монстров |
| `pname.dat` | 12 037 | 560 | var | ✅ decoded | имена props |
| `D6ITEM.DAT` | 243 956 | 859 | 284 | 🟡 частично | параметры предметов/атак |
| `D6MONS.DAT` | 278 800 | 820 | 340 | 🟡 частично | параметры монстров |
| `D6NPC.DAT` | 5 796 | 161 | 36 | ✅ ключ найден | NPC, id ↔ `CODEFILE.NNN` |
| `D6PROP.DAT` | 35 904 | 561 | 64 | 🟡 частично | архетипы интерактивных объектов |
| `D6TRLIST.DAT` | 13 380 | 223 | 60 | ✅ decoded | именованные лут-/магазинные листы |
| `D6TREAS.DAT` | 58 800 | 294 | 200 | 🟡 частично | записи сокровищ, 10 слотов × 20 Б |
| `D6HELM.DAT` | 14 856 | 24×16 | — | 🔴 новый | таблица шлем ↔ модель головы (u16-матрица, `0xFFFF` = пусто) |
| `D6MONSND.DAT` | 22 264 | 121 | 184 | ✅ **новый, decoded** | монстр-модель → набор звуков |
| `MONSOUND.DAT` | 32 609 | 742 | текст | ✅ **новый, decoded** | реестр SFX, **plain text, редактируемый** |
| `D6WORLD.DAT` | 19 656 | — | — | 🔴 новый | заголовок `u32 = 72000`, далее разрежённые данные; вероятно карта мира/сетка сегментов |
| `EVENTS.DCL` | 152 852 | 182 | — | ✅ **новый, decoded** | декларации событийного языка |
| `EVENTS.COD` | 7 646 | 182 | var | 🟡 адреса известны | байткод событий |
| `npccode/CODEFILE.*` | 1 495 674 | 158 | текст | ✅ **новый, decoded** | скрипты NPC, диалогов, квестов |
| `pctalk/TALKPAK.00N` | 1 338 ×10 | 46 | 12 | ✅ decoded | индекс `[id][offset][len]`, ссылки на речь PC |
| `speech.dat` | 1 088 675 888 | — | — | 🔴 закрыт | контейнер `SFFS`, озвучка (1.01 ГБ) |
| `root.dat` | 710 752 | — | — | 🔴 закрыт | контейнер `SFFS` |
| `compass.dat` | 154 760 | — | — | 🔴 закрыт | контейнер `SFFS` |
| `ROADBRID.DAT` | 3 101 | — | текст | ✅ **новый, decoded** | правила стыковки тайлов дорог/мостов |
| `SSPATH.DAT` | 74 | 5 | текст | ✅ decoded | пути к медиа-ресурсам |
| `gameopt.dat` | 84 | 21 | 4 | ✅ формат | настройки, 21 × `uint32` |
| `TERRDATA.*` | ~215 МБ | — | — | 🔴 закрыт | глобальный ландшафт: `.TEX .OBJ .QAD .GRD .TOB .LST .NFO` |

Легенда: ✅ формат подтверждён · 🟡 структура известна, семантика полей частично · 🔴 не декодирован

### 3.2. Общий паттерн таблиц `D6*.DAT`

Все фиксированные таблицы движка построены одинаково:

```
запись 0        — маркер: первый uint32 = количество используемых записей
запись 1..N     — рабочие данные
байты 0..21/23  — ASCII-имя (внутреннее, не локализуемое)
байты далее     — числовые поля, little-endian uint16
```

Из этого следует ключевое ограничение моддинга: **число записей зашито в файл и, вероятно, в `dlords.exe`**. Добавлять записи опасно, изменять существующие — относительно безопасно.

### 3.3. Строковые таблицы

```
uint32 count
count × { uint32 id; uint32 string_offset }
блок null-terminated строк, кодировка CP1251
```

Диапазоны id в `rd6string.dat`:

| Диапазон | Содержимое |
|---|---|
| 1100–1105 | атрибуты |
| 1300–1315 | расы |
| 1400–1434 | классы |
| 1600–1615 | категории существ |
| 1800–1844 | навыки |
| 2200–2215 | статусные эффекты |
| 3500+ | переходы между зонами, подсказки взаимодействия |
| 4650–4712 | эффекты ударов и снарядов |
| 4750–4765 | боевые/статусные эффекты |
| 4800/4850/4900/4950+ | слоты и категории предметов |
| 5000+ | форматные строки инвентаря и боя |
| 5600+ | сетевой интерфейс |
| 7000+ | создание персонажа, инвентарь |

### 3.4. Проблема ключей `iname.dat` ↔ `D6ITEM.DAT` (не решена)

Подтверждаю вывод прошлого отчёта: это **разные пространства id**.

| id | `iname.dat` | `D6ITEM.DAT` запись |
|---:|---|---|
| 4 | `CHAIN BOOTS` | `Vampire's Bite` |
| 8 | `AENIR` | `Heal Potion` |

Лут-таблицы (`D6TRLIST.DAT`, `D6TREAS.DAT`) ссылаются на **`iname.dat`**. Параметры предметов лежат в `D6ITEM.DAT`. Мост между ними пока не найден — вероятно, он внутри `dlords.exe` или в поле самой записи `D6ITEM.DAT`, которое ещё не идентифицировано. `items_catalog.csv` — рабочее сравнение, **не авторитетный join**.

Практический вывод: править лут-листы можно уже сейчас, править статы конкретного лутового предмета «по имени» — нельзя, пока мост не найден.

---

## 4. Событийная система мира: `EVENTS.DCL` / `EVENTS.COD`

Это слой мировых механизмов: двери, рычаги, ловушки, телепорты, головоломки, спавны, переходы между сегментами.

### 4.1. Структура `EVENTS.DCL` (расшифрована)

| Смещение | Размер | Содержимое |
|---|---|---|
| `0x0000` | 4 | `uint32 count = 182` |
| `0x0004` | 728 | 182 × `uint32` — смещения точек входа в `EVENTS.COD` |
| `0x02DC` | 3368 | нули (резерв) |
| `0x1004` | 7644 | 182 × `char[42]` — имена примитивов (`@NAME`) |
| `0x2E00` | — | нули |
| `0xB808` | 728 | 182 × `uint32` — кумулятивное число параметров |
| `0xE808` | 7432 | 182 упакованных null-terminated **описания на английском** |
| `0x10664` | 85 680 | 2040 × `char[42]` — имена параметров (1013 заполнено) |

`EVENTS.COD` — 7646 байт байткода. Смещения точек входа известны, семантика опкодов — нет. Средняя длина обработчика ≈ 42 байта, то есть это компактные декларативные записи, а не полноценный скрипт.

### 4.2. Что умеет событийный язык

182 примитива. Полный список с описаниями: `documentation/extracted/event_primitives.csv`.

Категории:

**Двери и створки (~35 примитивов)** — самая большая группа. Открытие с задержкой, двустворчатые двери, циклы «открыть-ждать-закрыть-ждать», условное открытие по состоянию:
`@OPENWCLOSE` (Open a door, delay, then close the door), `@LOPENWCLOSEW` (Repeat: open door, wait, close door, wait, until state=0), `@IFSTATEOPENELSECLOSE`, `@IFSTATEDBLOPENELSECLOSE`, `@WAITOPENWAITCLOSE`, `@SIMPLEOPENDOOR`, `@IFSTATEOPENWAITSWOFF`, …

**Состояния и переключатели** — `@SETWSTATE` (Set A World State), `@TOGGLEWSTATE`, `@SETASWITCH`, `@TOGGLESWITCH`, `@ENABLEASWITCH`, `@DISABLEASWITCH`, `@EQUATESWITCHTOSTATE`, `@EQUATESTATETOSWITCH`.

**Логика и комбинации** — `@TEST2SWITCHES`, `@TEST4SWITCHES`, `@TEST7SWITCHES`, `@TEST6STATES`, `@TEST3STATESTRUE`, `@TEST3STATESFALSE`, `@TESTOF4STATECOMBO` (Test 4 states via combination if equal set state), `@IFAANDBSETSTATEC`, `@IFAORBSETSTATEC`, `@IFANOTBSETCSETA`, `@IFNOTAANDNOTBSETSTATEC`.

**Зоны** — `@ENABLEBOUNDS`, `@DISABLEBOUNDS`, `@ONSTATEBOUNDS` (Enable/Disable BoundArea On State), `@ONNOTSTATEBOUNDS`, `@PARTYINBOUNDS`, `@IFOBJINBOUNDSTATEELSESWITCH`, `@AREAPUSHOUT`.

**Перемещение** — `@MOVETONAVPOINT` (Move Monster/PC towards a NavPoint), `@ROTATETONAVPOINT`, `@NOFACETONAVPOINT`, `@MOVEENTITY` (Move Entity Limited Distance), `@FALLENTITY`, `@CLIMBLADDER`, `@EXECTELEPORT`, `@PARTYTELEPORT`, `@TELEPORTMONSTER`, `@TELEPORTPROP`, `@BOARDSHIP`.

**Сегменты и переходы** — `@LOADSEGMENT`, `@FORCELOADSEGMENT`, `@LOADXSEGMENT`, `@LOADSTATESEGMENT`, `@SWITCHTOSEGMENT`, `@SWITCHDOORTOSEGMENT`, `@SWITCHDDTOSEGMENT` (If ALL in area then load in a New Segment, else flip switch), `@GOTOBSPONLY` (Teleport To BSPOnly), `@GOTOBSPTERR`, `@ENTERTHETOWN`.

**Монстры** — `@MAKEMONSTER` (Generate Monsters), `@SPAWNAMONSTER`, `@RELEASEMONGROUP` (Release Holding Monsters In Group), `@TESTMONEXIST`, `@SETMONVULNERABLE`, `@OBJECTSPELLMONSTER`, `@CREATEMONSTEREFX`, `@MOONBRIDGESPAWN`, `@SETGENENCSTATUS`.

**Предметы** — `@CREATEITEM` (Create An Item In The World), `@PLACEANITEM` (Place USEITEM In The World At WOCCUPIED Destination), `@EXCHANGEITEM`, `@CHANGEITEM2ITEM`, `@PLACEONEOFTWOITEMS`, `@PLACEONEOFFIVEITEMS`, `@PLACEONEEVILITEM`, `@USEANITEM`, `@USE1OF4ITEMS`, `@TAKEOCCUPIEDITEM`, `@IFHAVEANITEM`, `@IFNOTHAVEITEM`, `@IFISEQUIPPED`, `@IFNOTEQUIPPED`, `@NEWITEMATTACH`.

**Квесты и прогресс** — `@SETQUESTREG` (Set A PC QuestReg value), `@IFSTATESETQUESTREG`, `@IFNOTSTATESETQUESTREG`, `@IFQFLAGCALLEVENT`, `@IFNOTSTATEONQUESTCALLEVENT`, `@GIVEPCABIL` (Give PC Ability, Skill, Trait, Spell if !QFlag), `@SETGAMESTATUS`, `@GAMEOVER` (End The Game — Play Movie Ending).

**Именные головоломки** (уникальные механики уровней, каждая имеет свой примитив):
`@SNAKEBASKET` (Temple Snake Basket Dispenser), `@SNAKEHEADTEST`, `@SNAKELIFT` (Activate snake head lift), `@TESTOF4IDOLS` (Test 4 Idols At WOCCUPIED+n with ITEM[n]), `@DRAGONCRYSTALTEST`, `@TRANSFORMTHEMASK`, `@CHESSMANMOVE`, `@RESETCHESSPUZZLE`, `@KNIGHTROOMMOVE`, `@TESTJUMPRUNES`, `@PIVOTBRIDGE`, `@TEST6OCCUPIEDS`, `@BASEDESTLIGHTBEAM`, `@PROPBONELIGHTBEAM`, `@SETCRATEEXPLODE`.

**Эффекты, звук, окружение** — `@OBJECTEFXINIT`, `@OBJECTEMITEFXINIT`, `@DESTTOOBJEFXINIT`, `@DESTTOOBJSPELLINIT`, `@SPECIALEFFECT`, `@ADDEMITLIGHT`, `@BLASTAREA`, `@MAGICPOOL`, `@MAGICFIRE`, `@PLAYSOUND`, `@PROPSOUND`, `@SETWEATHER` (0-Clear 1-Rain 2-Snow), `@TEXTMSG`.

**Управление потоком** — `@CALLEVENTLIST` (Call a list of Events), `@DELAYCALLEVENT`, `@LCALLEVENTDELAY`, `@ACTIVATEEVENT`, `@IFSTATECALLEVENT`, `@IFSTATECALLAELSECALLB`, `@LEFFECTDELAY`, `@LOOPEFXDELAY`, `@STARTWTIMER`.

### 4.3. Словарь параметров

1013 использований, ключевые имена:

| Параметр | Смысл |
|---|---|
| `!STATE`, `!STATEA..D`, `STATUS` | мировые состояния (world states) |
| `!SWITCH`, `SWSTATUS` | переключатели |
| `!BOUNDNUM` | номер зоны (bound area) |
| `!EVENTA..D` | ссылки на другие события |
| `!WOCCUPIED`, `!WOCCA..D` | «занятые» слоты мира (постаменты, гнёзда под предмет) |
| `DOOR`, `DOORA`, `DOORB`, `SPEED` | объекты дверей и скорость анимации |
| `NAVPNT`, `DESTNAV`, `LASTNAV` | навигационные точки |
| `BSPNUM`, `SEGMENT`, `SEGSWITCH`, `SEGSTATUS` | BSP-блок и сегмент мира |
| `XTILE`, `YTILE`, `ZTILE`, `XPOS`, `YPOS`, `ZPOS`, `YROT`, `YOFFSET` | координаты |
| `MONREC`, `MONA..D`, `MONINIT`, `MAXSLOT`, `MAXCOUNT` | спавн монстров |
| `ITEM`, `XITEM`, `USEITEM`, `ITEMA..D` | предметы |
| `EFX`, `SFX`, `SPELL`, `SFXREC` | эффекты и звуки |
| `MSG`, `MSGONE`, `MSGTWO`, `TIME`, `DELAY`, `OPENDELAY`, `CLOSEDELAY` | текст и тайминги |
| `POOL`, `FIRE`, `RADIUS`, `DAMAGE`, `POISON` | площадные эффекты и урон |
| `COMBO`, `PROPID`, `TWIDTYPE`, `VALUE`, `TDATA`, `OBJNUM` | головоломки и props |

> Ограничение: кумулятивный индекс параметров (`0xB808`) даёт корректное **количество** параметров на событие, но привязка блоков смещена на 1–2 позиции. Порядок параметров в потоке восстанавливается вручную по смыслу (сверено на `@TEXTMSG` = `MSG,TIME,UNUSED` и `@MAKEMONSTER` = `MONREC,XTILE,YTILE,ZTILE,BSPNUM,MONINIT,MAXSLOT,MAXCOUNT,ABSFLAG`). Для полной автоматизации нужен ещё один проход.

### 4.4. Региональная привязка

Экземпляры событий расставлены по регионам. Слотов — 64 на группу (`00`–`63`), заполнены не все:

| Группа | Файл | Роль | Заполнено |
|---|---|---|---:|
| TRIG | `D6TRIGxx.DAT` | триггеры | 30 |
| SWIT | `D6SWITxx.DAT` | переключатели/состояния | 31 |
| BOUN | `D6BOUNxx.DAT` | границы и переходы | 30 |
| TRAP | `D6TRAPxx.DAT` | ловушки | 21 |
| SPEC | `D6SPECxx.DAT` | спец-логика региона | 10 |
| LINK | `D6LINKxx.DAT` | связи | 0 (все пустые) |

Пример нагрузки региона 00: `D6TRIG00.DAT` — 401 триггер (73 968 Б), `D6BOUN00.DAT` — 140 границ, `D6TRAP00.DAT` — 64 ловушки, `D6SWIT00.DAT` — 40 переключателей.

Размер записи в этих файлах **переменный** — деление размера на count не даёт целого числа. Значит внутри записей есть строки или списки переменной длины. Инвентаризация: `documentation/extracted/region_files.csv`.

---

## 5. Система NPC, диалогов и квестов — `npccode/`

Самая ценная находка. Это полный, читаемый исходник квестовой логики.

### 5.1. Формат контейнера

```
повторяется до конца файла:
    uint32 line_tag     — сквозной счётчик/адрес строки для goto
    uint32 length       — длина блока
    char[length]        — null-terminated ASCII-строка исходника
```

158 файлов, все парсятся без остатка. `CODEFILE.NNN` соответствует записи `NNN` в `D6NPC.DAT`.

Расшифрованные скрипты: `documentation/extracted/npc_scripts/npc_001.txt` … `npc_158.txt`.

### 5.2. Язык скриптов

90 операторов. Полный список с частотой: `documentation/extracted/npc_script_statements.csv`.

**Управление потоком**
`if / else / endif`, `goto $LABEL`, `onexprgoto`, `onact <act> $LABEL`, `onreply $A $B $C`

**Обработчики действий игрока** (13 хуков, есть у каждого NPC)
`act-inittalk`, `act-talk`, `act-donetalk`, `act-exit`, `act-alone`, `act-attack`, `act-steal`, `act-use`, `act-giveitem`, `act-givegold`, `act-buyitem`, `act-sellitem`, `act-donetrade`

**Диалог**
`msg "…"` — реплика · `blurbmsg "…"` — фраза мимоходом · `qa "…"` — вопрос с вариантами · `onreply` — ветвление ответа · `newmsg`, `addmsg`, `outmsg`, `killmsgq`, `cleardialog`, `priorityqa`, `talkkey`, `talkmode`, `greet`, `goodbye`

**Темы разговора (лексикон)**
`clearlexiop` · `addlexiop "ТЕМА"` · `enablelexiop` · `disablelexiop(-N) "ТЕМА"`
Именно так реализовано «открытие новых тем» — NPC получает тему заранее, но отключённой; событие включает её.

**Состояние и флаги**
`setflag`, `subflag`, `addflag` — локальные флаги NPC
`setpflag`, `setnpcpflag`, `partysetpflag` — флаги персонажа/партии
`setcflag`, `addcflag`, `subcflag` — флаги разговора
`setbflag` — поведенческие (`%BFLAG_FRIENDLY`, `%BFLAG_ATTACKGREET`, `%BFLAG_NOSELECT`)
`settflag` — таймерные
`setwflag` — мировые
`setqflag(-1)(%QUEST_X)(N)` — **регистр квеста**
`setglobalflag` — глобальные

**ИИ и поведение**
`findtarget(mode)(range)`, `destnav`, `setdest(%SD_BSP)(x)(y)(z)`, `setmode`, `setdir`, `facedir`, `attack`, `passive`, `vulnerable`, `collide`, `flee`, `run`, `fly`, `teleport`, `vanish`, `pcally`, `ignore`, `interrupt`, `delay`, `encrange(N)`, `byerange(N)`, `killlocq`, `suicide`, `fightfoe`

**Транзакции и прогресс**
`giveitem`, `takeitem`, `dropitem`, `equipitem`, `givegold`, `takegold`, `tradeflag`, `tradepc`, `setclass`, `questclass`, `checkclass`, `setpcdata`, `expbonus`, `showquest`, `trainpc`, `addtrainop`, `cleartrainop`, `heraldry`, `jailhouse`, `npcaddnewkey`, `maptag`

**Презентация**
`playanim`, `propanimate`, `playefx`, `playsfx`, `castspell`, `setfade`, `setmbits`

### 5.3. Квестовые регистры

**79 регистров** `%QUEST_*`. Регистр — счётчик стадии (`setqflag(-1)(%QUEST_X)(N)`, проверка `if qflag(-1)(%QUEST_X) > (1)`).

Полный список: `documentation/extracted/quest_registers.csv`. Разбивка по смыслу:

*Сюжетная линия (главная):*
`%QUEST_VALDANE` (23) · `%QUEST_ARGALIA` (27) · `%QUEST_NARAKO` (40, самый используемый) · `%QUEST_GALDRYNHORN` (21) · `%QUEST_HORNRETURN` · `%QUEST_VORAATUS` · `%QUEST_MALOKAN` · `%QUEST_SHADOWLORD` · `%QUEST_SHADOWGEM` · `%QUEST_TOTEM` · `%QUEST_GRYMLOK` · `%QUEST_SEANCE` · `%QUEST_VETRIAN` · `%QUEST_ELVITHRA` · `%QUEST_TOMBENTRY` · `%QUEST_CIRCLESTONES` · `%QUEST_BIGBADMOG` · `%QUEST_VAMPI`

*Гильдии — вступление и ступени:*
`FIGHTGUILD/FIGHTJOIN/FIGHTTWO` · `MAGEGUILD/MAGEJOIN/MAGETWO` · `PRIESTGUILD/PRIESTJOIN/PRIESTTWO` · `THIEFGUILD/THIEFJOIN/THIEFTWO` · `SISTERGUILD/SISTERJOIN/SISTERTWO` · `BUSHIGUILD/BUSHITWO`

*Классовые квесты (по одному на класс):* `KNIGHT`, `MARAUDER`, `LORD`, `DEATHLORD`, `SORCERER`, `BATTLEMAGE`, `WIZARD`, `WARLOCK`, `CELESTIAL`, `PALADIN`, `STARGAZER`, `CRUSADER`, `SAMURAI`, `IMPERIAL`, `SHUGENJA`, `MONK`, `BUDOKA`, `HATAMOTO`, `WARLORD`, `KENJASAI`, `SHAOLINMASTER`, `NINJALORD`, `VALKYRIE`, `ENCHANTRESS`, `WARWITCH`, `HUNTER`, `TRICKSTER`, `RANGERLORD`, `CABALIST`

*Побочные:* `ALEISTERLETTER`, `AUGUSTUS`, `BLOODVIAL`, `CARDONE/CARDTWO/CARDTHR`, `CUSTARDMAP`, `DHARA`, `DRAGONEGG`, `FLASK`, `GILEAH`, `MARA`, `OKOTTA`, `SHARIA`, `THIEFFREE`

### 5.4. Квестовые предметы

72 символических имени `%ITEM_*` — предметы, на которые прямо завязана квестовая логика:

`ARGALIA`, `SHADOWAMULET`, `SHADOWGEM`, `SHADOWSWORD`, `SHADOWPOWER`, `TOTEM`, `TREETOTEM`, `SUMMONTREE`, `HORN`, `DRAGONEGG`, `CODEX`, `MOONCODE`, `RELICRING`, `EMMINDORRING`, `FIRESWORD`, `ELFSWORD`, `STAFF`, `ROD`, `WAND`, `MIRROR`, `HEART`, `PAINTING`, `DOLL`, `CANDLE`, `POWDER`, `FLASK`, `BLOODVIAL`, `EMPTYVIAL`, `CLARITY`, `DISPELMAGIC`, `PACKAGE`, `PRIZE`, `ROBES`, `SCARFACE`, `STORMS`, `VARTUGGEYE`, `YAMAGIFT`, `ELVITHRAGIFT`, `NARAKO`, `MARALETTER`, `ALEISTERLETTER` (через `LETTER`), `ORDERS`, `SUMMONS`, `FATHIENPASS`, `CUSTARDMAP`
Ключи: `ARININNKEY`, `FARINNKEY`, `CEMETERYKEY`, `DEMONKEY`, `MANSIONKEY`, `SANCTUMKEY`
Камни: `GEMA`–`GEME`, `GEMSTONE1`–`3`, `GEMSTONEA`–`D`, `ECRYSTAL`, `FIRSTCRYSTAL`, `GEMSTONE`

### 5.5. Темы диалогов

112 тем `addlexiop`. Полный список: `documentation/extracted/dialogue_topics.csv`.

Сюжетные (восстанавливают завязку кампании):

- `I SEEK ELLOWYN OF DAVENMOR` — поиск Эллоуин, дочери лорда Давенмора
- `I SEEK ELLOWYN, DAVENMOR DAUGHTER`, `I SEEK THE LADY ELLOWYN`, `TELL ME ABOUT ELLOWYN`
- `ELLOWYN ESCAPED FARGROVE`, `SHARIA HELPED ELLOWYN ESCAPE`, `WHERE DID YOU TAKE ELLOWYN`
- `I SEEK VALDANE, LOVER OF ELLOWYN`
- `EMMINDOR SENDS REGARDS`, `I SEEK THE WIZARD EMMINDOR`, `I SEEK AUDIENCE WITH EMMINDOR`
- `I BRING NEWS OF THE ARGALIA`, `SHOW THE ARGALIA OF ERYLDORN`, `ASK ABOUT ARGALIA OF ERYLDORN`
- `I HAVE GALDRYN'S HORN`, `SHOW GALDRYN'S HORN`
- `HELP LORD DAVENMOR AND FARGROVE`, `SHOW DAVENMOR'S ORDERS`, `PETITION LORD GALEBRIAND`
- `I SEEK THE COUNCIL OF ELDERS`, `I SEEK THE LOST EAGLE`, `CAPTAIN OKATTA IS TROUBLE`
- `NARAKO WAITS AT THE INN`, `I SEEK SISTER DHARA`, `GIVE DHARA'S SPECIAL PACKAGE`
- `I WALK THE PATH OF THE TIGER`

Сервисные: `TRADE` (17 NPC), `RENT A ROOM`, `PAY JAIL FINE`, `BAIL OUT DERLINGER`, `MAKE DONATION`, `TELL FORTUNE`, `DRINK RED GHAR'S ALE`, `DRINK ELVEN TEA`, `BUY SCROLL OF DISPEL MAGIC`.

Обучающие/классовые: `FIGHTER TRAINING`, `STUDY MAGIC`, `CELESTIAL GUIDANCE`, `LESSONS OF THE MASTER`, `SECRETS OF THE SISTERHOOD`, `TRICKS AND TRAPS` + 29 тем `<CLASS> CLASS`.

### 5.6. Опознанные NPC

Из `qa "I am …"` внутри скриптов:

| CODEFILE | NPC | Роль |
|---|---|---|
| 001 | **Staroxia**, Seer of the Stars | сюжетный оракул; выдаёт квест Shadow Lord |
| 006 | Lord Graemare of ~Rothn~ | сюжет |
| 014 | Sir Grunmeir | гильдия воинов + магазин |
| 016 | Aleister | гильдия магов |
| 017 | Seer Paulus | храм / целестиальная гильдия |
| 057 | Narako of the House of Misume | сюжет (`%QUEST_NARAKO`) |
| 058 | Elvithra | сестринство |
| 060 | Deliah Irons | гильдия воров |
| 062 | Lady Chana | сестринство (второй город) |
| 064 | Sir Nil-Galand | гильдия воинов (второй город) |
| 065 | Orlan Drey | целестиальная гильдия (второй город) |
| 075 | Valdane Graemare of Rothn | сюжет |
| 077 | Ellowyn | сюжетная цель |
| 093 | Wuldenfyr | — |
| 108 | член тайного женского общества | сестринство |
| 119 | Feros Duul | — |
| 124 | Sir Falen | — |
| 126 | Talya | — |
| 141 | Uriel | — |
| 142 | Palomir | эльфийский торговец (совпадает с `Palomir's SHOP #1/2/3` в `D6TRLIST.DAT`) |

Индекс всех 158: `documentation/extracted/npc_script_index.csv`.

### 5.7. Пример реальной квестовой цепочки

Из `npc_001.txt` (Staroxia), квест на класс Shadow Lord — полная цепочка условий:

```
if qflag(-1)(%QUEST_SHADOWGEM) > (1)
  if qflag(-1)(%QUEST_SHADOWLORD) ! (3)
    if pflag(%PFLAG_SHADHINT) = (0)
      if haveitem(%ITEM_SHADOWAMULET) = (1)
        goto $HINTSHADOWLORD
...
msg "Attributes: Strength 40, Intellect 40, Dexterity 40, " +
if checkclass(4)(4)(CLASS-SHADOWLORD) = (1)   → $SHADOWASK
qa  "You have met these requirements, do you wish to quest …"
onreply $SHADOWQUEST $NOQUEST $EXIT
setqflag(-1)(%QUEST_SHADOWLORD)(1)
msg "You must return to the Isle of the Damned with the Amulet…"
...
setqflag(-1)(%QUEST_SHADOWLORD)(3)
msg "I have seen your battle with the Dracolich, and your …"
setclass(4)(CLASS-SHADOWLORD)
giveitem(%ITEM_SHADOWPOWER)
```

Также из скрипта Staroxia восстанавливается география мира: `Shadow Ruins` (на Eastern Range, за Battlefields of the Dead), `Sea of Woe` (севернее Shadow Ruins), `Isle of the Damned`, `Vale of Ruin`, `Sagathian Moors`, `Mountains of Despair`, `Northlands` (Grymlok's Tower), `Southern Boulders`, `Forbidden Lands`, `Netherlands` (Crystal Stone), `Guardians of the Forest`, `Relics of Power`.

---

## 6. Классы и прогрессия — полная расшифровка

Система: **4 ступени**. Ступень 1 — базовый класс, ступени 2–3 — специализация, ступень 4 — элита. Каждый переход требует (а) порога атрибутов, (б) выполнения классового квеста.

Механика в скрипте:
```
checkclass(tier)(?)(CLASS-X)  → проверка требований
setqflag(-1)(%QUEST_X)(1)     → выдача квеста
setqflag(-1)(%QUEST_X)(3)     → квест выполнен
setclass(tier)(CLASS-X)       → присвоение класса
setpcdata(-1)(5)(%HERALDRY_X) → геральдика/герб
```

### 6.1. Дерево классов

| Гильдия | NPC | Ступень 1 | Ступень 2/3 | Ступень 4 (элита) |
|---|---|---|---|---|
| Воины | Sir Grunmeir (014), Sir Nil-Galand (064) | Fighter | Knight, Marauder | **Lord**, **DeathLord** |
| Маги | Aleister (016), NPC 066 | Mage | Sorcerer, BattleMage | **Wizard**, **Warlock** |
| Храм | Seer Paulus (017), Orlan Drey (065) | Priest | Celestial, Paladin | **Stargazer**, **Crusader** |
| Воры | Deliah Irons (060), NPC 090 | Thief | Hunter, Trickster | **Ranger Lord**, **Cabalist** |
| Буши | NPC 056, 061 | — | Samurai, Imperial, Shugenja, Monk, Budoka | **Hatamoto**, **Warlord**, **Kenjasai**, **Shaolei Master**, **Ninja Lord** |
| Сестринство | Elvithra (058), Lady Chana (062) | — | Valkyrie, Enchantress | **War Witch** |
| — (скрытый) | Staroxia (001) | — | — | **Shadow Lord** |

### 6.2. Требования по атрибутам

Извлечено дословно из текста NPC. Полная таблица: `documentation/extracted/class_advancement.csv`.

| Класс | Ступень | Str | Int | Dex |
|---|---:|---:|---:|---:|
| Sorcerer | 2/3 | 15 | 30 | 25 |
| Trickster | 2/3 | 15 | 30 | 25 |
| Shugenja | 2/3 | 15 | 25 | 25 |
| Celestial | 2/3 | 20 | 25 | 20 |
| Enchantress | 2/3 | 20 | 30 | 20 |
| BattleMage | 2/3 | 20 | 25 | 25 |
| Hunter | 2/3 | 20 | 25 | 25 |
| Samurai | 2/3 | 20 | 20 | 25 |
| Monk | 2/3 | 20 | 20 | 25 |
| Knight | 2/3 | 25 | 20 | 20 |
| Imperial | 2/3 | 25 | 20 | 20 |
| Paladin | 2/3 | 25 | 25 | 20 |
| Marauder | 2/3 | 25 | 15 | 25 |
| Budoka | 2/3 | 25 | 15 | 25 |
| Valkyrie | 2/3 | 25 | 25 | 25 |
| **Stargazer** | 4 | 30 | 45 | 35 |
| **Wizard** | 4 | 30 | 45 | 40 |
| **Kenjasai** | 4 | 30 | 45 | 40 |
| **Cabalist** | 4 | 30 | 45 | 45 |
| **Shaolei Master** | 4 | 30 | 35 | 45 |
| **Warlock** | 4 | 35 | 40 | 40 |
| **War Witch** | 4 | 35 | 45 | 40 |
| **Hatamoto** | 4 | 35 | 35 | 45 |
| **Ranger Lord** | 4 | 35 | 40 | 45 |
| **Lord** | 4 | 40 | 30 | 35 |
| **Crusader** | 4 | 40 | 40 | 35 |
| **Warlord** | 4 | 40 | 35 | 35 |
| **Ninja Lord** | 4 | 40 | 30 | 45 |
| **Shadow Lord** | 4 | 40 | 40 | 40 |
| **DeathLord** | 4 | 45 | 30 | 35 |

> Ограничение: в `CODEFILE` строка требований оборвана на `" +` (продолжение хранилось в исходнике и в скомпилированный файл не попало). Поэтому Str/Int/Dex восстановлены полностью, а Agility/Vitality, требования по уровню и по навыкам — нет. Их нужно брать из `Manual/HTML/AppendixB.htm` или из рантайма.

---

## 7. Персонаж: расы, атрибуты, навыки

### 7.1. Атрибуты

Strength (Сила), Intelligence (Разум), Dexterity (Ловкость), Agility (Быстрота), Vitality (Здоровье), Honor (Честь).

> Расхождение терминологии: в скриптах NPC используется **Intellect**, в `rd6string.dat` — Intelligence/Разум. Это один и тот же атрибут.

### 7.2. Расы и стартовые параметры (из мануала)

| Стат | Human M | Human F | Urgoth | Dwarf | Wylvan | Elf M | Elf F | Zaur | Thrall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Strength | 15 | 13 | 20 | 18 | 11 | 12 | 10 | 17 | 10 |
| Intelligence | 12 | 14 | 8 | 10 | 13 | 15 | 17 | 9 | 14 |
| Dexterity | 13 | 13 | 9 | 12 | 14 | 15 | 15 | 10 | 16 |
| Agility | 12 | 13 | 9 | 10 | 16 | 14 | 15 | 14 | 16 |
| Vitality | 14 | 12 | 20 | 16 | 11 | 10 | 8 | 16 | 10 |
| Honor | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 |
| Life | 48 | 44 | 60 | 52 | 42 | 40 | 36 | 52 | 40 |
| Hit | 13 | 13 | 9 | 12 | 14 | 15 | 15 | 10 | 16 |
| Speed | +0 | +2 | +0 | +0 | +10 | +5 | +7 | +5 | +10 |
| Parry | 1 | 1 | 0 | 0 | 2 | 2 | 2 | 1 | 3 |
| Influence | 10 | 11 | 10 | 10 | 10 | 10 | 11 | 10 | 10 |

`Grendol` и `Race8..Race15` есть в `rd6string.dat`, но в таблице мануала отсутствуют — неиграбельные/вырезанные.

Практическое чтение таблицы: Urgoth — чистый танк (Str/Vit 20, Parry 0). Thrall — лучший по подвижности (Agi/Dex 16, Speed +10, Parry 3), но 40 HP. Elf F — максимум Int (17) при худшей живучести (36 HP). Human — единственная раса без провальных статов.

### 7.3. Навыки (id 1800–1844)

45 навыков. Группы: рукопашный бой (2), оружие (9), защита (7), атлетика/утилита (6), воровство (6), магия (8), пассивные/демонические (7).

Подтверждённые зависимости:

| Навык | Требование |
|---|---|
| Backstab | Stealth 3 |
| Trap Disarm | Inspect |
| Lockpicking | Inspect |
| Alchemy | Nether Magic 1 |
| Channel | Celestial Magic 1 |
| Scribe | Arcane Magic 1 |
| Magic Weapon | Light Weapon 1 |

Athletics по уровням: 1 — прыжок в сторону, 2 — кувырок вперёд, 3 — кувырок в сторону, 4 — сальто назад, 5 — максимальная скорость бокового/заднего движения.

> В мануале противоречие: `AppendixC.htm` даёт side roll на уровне 3, `MainPage` — на уровне 2. Проверять в рантайме.

Оружейные навыки на уровне 5 открывают усиленные атаки для нескольких семейств оружия. Навыки брони и щитов снимают штрафы за экипировку.

### 7.4. Статусы и боевые эффекты

**Статусы (2200–2215):** Sleep, Fear, Stun, Paralysis, Blindness, Madness, Poison, Disease, Charm, Infection, Curse, Possession, Freeze, Drunk + 2 неиспользуемых слота.

**Каналы урона:** Magical Strike, Fire Strike, Rune Strike, Nether Strike, Ice Strike.

**Разряды снарядов:** orange, pink, plasma, arrows, fire, smoke, lightning, magic, ice, nether, vampirism.

**Боевые события:** critical strike, weapon break, bleeding, entangled, petrified, confused.

**Сопротивления (из мануала):** magic, fire, petrification-группа, poison, ice, gas. Снижают и урон, и длительность эффекта.

---

## 8. Магия

4 школы: Arcane, Celestial, Nether, Rune. 103 заклинания извлечено из мануала → `documentation/research_export/manual_spells.csv` (поля: school, name, level, recipe, effect, type).

Nether — единственная школа с рецептами (алхимические компоненты). Это подтверждается лут-листами: `Sister Dhara's #2/#3/#4` торгует `SNAKE SKIN`, `RAVEN CLAW`, `MONKEY PAW`, `DRAGON TOOTH`, `DEMON HORN`, `SOUL STONE`, `MANDRAKE ROOT`, `BAT WING`, `RAT TAIL`.

Цепочка исполнения заклинания в движке (по `DEBUG.LOG` и структуре ресурсов):

```
навык школы → книга/свиток/предмет → назначение в quick menu → каст (ЛКМ)
   → SPELL id
   → InitSPELL_EFX / EFXLIST      визуальный эффект (efxgfx/*.al8, sprites/)
   → InitSPELL_PARTICLE / EMITTERS частицы
   → InitSPELL_PROPEFX             эффект на объектах мира
   → SFX id → MONSOUND.DAT → sounds/*.wav (через Miles)
   → combat/status система: урон, статус, сопротивление
```

Заклинания также доступны событиям мира (`@OBJECTSPELLMONSTER`, параметр `SPELL`) — то есть ловушки и объекты кастуют те же заклинания.

---

## 9. Предметы, лут, торговля

### 9.1. Три независимых слоя

1. `iname.dat` — 948 публичных имён (предметы, заклинания). **Ключ лут-системы.**
2. `D6ITEM.DAT` — 858 записей параметров. **Другой ключ.**
3. `D6TRLIST.DAT` / `D6TREAS.DAT` — таблицы выдачи, ссылаются на слой 1.

### 9.2. Классификация `D6ITEM.DAT` по полю `u16_44`

| Значение | Группа |
|---:|---|
| 1 | оружие / атака |
| 2 | боеприпасы |
| 3 | броня / одежда |
| 4 | щиты |
| 5 | украшения, кольца |
| 6 | свитки, спец-использование |
| 7 | зелья |
| 10 | книги, книги заклинаний |
| 12 | золото, контейнеры |

Кандидаты полей: `u16_48` — иконка/модель, `u16_50` — качество/тир, `u16_76/80/84` — боевые характеристики, `u16_88` — цена, `u16_112/114` — флаги и требования.

Опорные точки: `Short Sword` → 75, `Katana` → 450, `Leather Armor` → 250, `Heal Potion` → 50, `Vampire's Ring` → 20000.

### 9.3. Лут-листы `D6TRLIST.DAT` — полностью читаемы

222 именованных списка, каждый до 18 предметов. Это самая доступная для правки система баланса в игре.

Типы списков:
- **По тиру и редкости:** `Common L1 Weapon(1)`, `Common L1 Weapon(2)`, `Rare L1 Weapons`, `Rare L1 Potion`, `Rare L1 Scroll`, `Spellbook (Any)`
- **По региону:** `Fathien Comm Armor`, `Fathien Rare Weap1`, `Fathien Rare Katal2`, `Fathien Comm Katal`, `Grunmier Weapons #2`, `Elven Rare Jewelry`
- **Магазины:** `DLORD Grunmeir SHOP`, `Palomir's SHOP #1/#2/#3`, `Sister Dhara's #2/#3/#4`

Магазины и дроп используют **один и тот же механизм** — это упрощает моддинг: правка одного списка меняет и ассортимент, и выпадение.

### 9.4. Сокровища `D6TREAS.DAT`

293 записи × 10 слотов × 20 байт (10 × uint16).

| Поле | Смысл (рабочая гипотеза) |
|---|---|
| `u16_0` | тип слота |
| `u16_1` | шанс (обычно 50 или 100) |
| `u16_2` | id предмета при типе 3 |
| `u16_6` | id предмета/списка при типах 1 и 2 |
| `u16_8` | обычно 100 — количество или базовый шанс |

Примеры: запись 1 → `WOOD ARROW`; 3 → `SKULL KEY, BLADED MACE, DRAGON HELM, GOLD`; 10 → `BRIMGULDEN'S HORN`; 19 → `SHADOW LORD AMULET, SOUL STONE, KNAVE OF WANDS`.

### 9.5. Дроп с монстров — не доказан

`u16_334` в `D6MONS.DAT` попадает в диапазон id лут-листов и коррелирует по семействам (гоблины → одни списки, скелеты → другие). Но это может быть таблица дропа, таблица экипировки, региональная привязка или профиль ИИ.

Проверка требует запуска: изменить кандидатное поле у одного слабого монстра на очевидный предмет и убить его несколько раз.

---

## 10. Монстры

820 записей в `D6MONS.DAT` (819 рабочих), 435 отображаемых имён в `mname.dat`. Разница означает, что многие записи — варианты одного существа (разные уровни, регионы, элитные версии).

Карта полей записи (340 байт):

| Смещение | Содержимое |
|---|---|
| 0–21 | внутреннее имя |
| 44–58 | блок характеристик |
| 76–106 | сопротивления/иммунитеты (типовые значения 25, 50, 80, 90, 100) |
| 108, 112 | класс существа / профиль ИИ |
| 116 | HP/уровень (у боссов и статичных объектов — 9999) |
| 120 | награда/сложность (типовые 120, 500, 1000, 5000) |
| 122–130 | урон, тип атаки, флаги |
| 334 | кандидат ссылки на лут-лист |

Опорные точки: `Graveyard Skeleton` → награда 120 · `Demon Dog` → 5000 · `Brimstone Hellcat` → 5000 · `Spirit Of Nivius` → множество сопротивлений 100 и 9999 в поле 116 (неубиваемый сюжетный объект).

### 10.1. Звук монстров — расшифровано

`D6MONSND.DAT`: 121 запись × 184 байта.

```
uint32 model_id            — модель монстра
char[24] soundset_name     — читаемое имя набора
int16[]                    — id звуков из MONSOUND.DAT по слотам (idle, attack, hit, death…)
```

Примеры наборов: `DLORDS SILENT`, `DLORDS STATUE`, `DLORDS GOBLIN`, `DLORDS DEMONDOG OLD`, `DLORDS ELF/GUARD`, `DLORDS DRUID`, `DLORDS TROLL OGRE`, `DLORDS KILLER BEE`, `DLV14 THRALL`, `DLV14 SMALL SNAKE`, `DLV15 SWAMPCREATURE`.

Суффиксы `(OLD)` и префиксы `DLV14`/`DLV15` показывают историю разработки: наборы версии 14/15 заменяли старые.

Экспорт: `documentation/extracted/monster_soundsets.csv`.

### 10.2. Реестр звуков `MONSOUND.DAT` — plain text

Это **не бинарный файл**, а комментированный текстовый конфиг с 742 слотами:

```
742             * MAXIMUM # OF SOUND RECORDS
0,"",11025,                                     * SFX_0
11,"spell_fireball.wav",22050,R,                * DLORDS FIREBALL SFX_FIREBALL  11
16,"spell_magic_missile.wav",22050,R,           * DLORDS MAGICMISSILE SFX_MAGICMISSILE 16
49,"splash_6x.wav",11025,R,                     * SFX_SWIM     49
-1,""                                           * END OF SOUNDS
```

Формат строки: `id,"файл.wav",частота[,R],  * комментарий`
`R` = resident (предзагрузка в память). `*` = комментарий. `-1` = конец таблицы.

**Это самая доступная точка модификации во всей игре** — заменяется текстом, без бинарных правок. Экспорт в CSV: `documentation/extracted/sound_registry.csv`.

---

## 11. Мир, уровни, ландшафт

### 11.1. Двухслойная структура

**Слой 1 — глобальный ландшафт.** `TERRDATA.*` (~215 МБ):

| Файл | МБ | Роль |
|---|---:|---|
| `TERRDATA.TEX` | 105 | атлас текстур ландшафта |
| `TERRDATA.GRD` | 41 | сетка высот |
| `TERRDATA.OBJ` | 32 | объекты на ландшафте |
| `TERRDATA.QAD` | 27 | quad-дерево / LOD |
| `TERRDATA.TOB` | 0.1 | таблица объектов |
| `TERRDATA.LST` | 0.05 | список размещений (float-координаты + id) |
| `TERRDATA.NFO` | 0.01 | метаданные |

Дополняют: `terrtex_BLEND/`, `terrtex_TF/`, `terrmap/`, `PathMap/*.PTH` (21 файл), `roadway/`, `ROADBRID.DAT`, `sky/`, `WaterArt/`.

`ROADBRID.DAT` — текстовые правила автостыковки тайлов дорог и мостов:
```
Combo[0].bridgeCombo[0][0] BCombo:0 OX:0 OY:-1  BRot:0 BFlip:0 RotTest:0
```
То есть дороги и мосты собираются процедурно из комбинаций тайлов со смещением, поворотом и отражением.

**Слой 2 — интерьеры и локации.** 40 наборов уровней, каждый — 11–13 файлов с общим базовым именем:

| Расширение | Роль |
|---|---|
| `.bsp` | геометрия / разбиение пространства |
| `.twd` | world/terrain-данные (самые тяжёлые, 325 МБ суммарно) |
| `.lf` / `.lfs` | level files / streamed |
| `.ls` / `.lss` | level segments / states |
| `.nvs` | навигация и видимость |
| `.lgt` | освещение |
| `.rgb` | цвет / вспомогательный свет |
| `.db` | база данных уровня |
| `.int` | интерьер/интеграция |
| `.l2n` | маппинг уровень→имена/номера |
| `.bol` | размещённые объекты и границы |

### 11.2. Список уровней

Города и поселения: `DLTownMAIN72`, `DLTownCHURCH32`, `DLTownMANORA30`, `DLTownMANORB08`, `DLTownSEWER129`, `DLTownTHIEF11`

Интерьеры: `Inn21`, `interior_inn23`, `interior_houseA02`, `interior_houseB03`, `interior_jail04`, `interior_mage16`, `interior_temple12`, `interior_weaponshop11`, `interior_apothecary04`, `interior_curio10`, `interior_agustus08`, `interior_dojo06`, `interior_MANOR66`, `Apothecary07`, `Dojo02`, `Temple05`, `weapon05`, `Mansion20`

Подземелья и сюжетные локации: `crypt32`, `Tomb20`, `Tower22`, `mazeA17`, `oldkeep79`, `moors79`, `guilddungeon30`, `dungc193`, `dungc180at512`, `VartuggFortress17`, `Naga_Chamber_Final26`, `Khadschamber34`, `GaldrynsChamber18`, `DLShadowRuinsB97`, `shadowrealmv0`, `swampinterior_south_only14`

Названия прямо соответствуют событийным примитивам: `Naga_Chamber_Final26` ↔ `@SNAKEBASKET`/`@SNAKELIFT`/`@SNAKEHEADTEST`, `GaldrynsChamber18` ↔ `%QUEST_GALDRYNHORN`, `DLShadowRuinsB97` + `shadowrealmv0` ↔ `%QUEST_SHADOWLORD`.

### 11.3. Props

`D6PROP.DAT`: 561 запись × 64 байта, имя в байтах 0–21.

Примеры: `Switch`, `Lever`, `Lock`, `Skull Lock`, `Keycard Reader`, `Keyboard`, `Monitor`, `Reactor Up`, `Reactor Down`, `Column (Full)`.

> Обратите внимание: `Keycard Reader`, `Keyboard`, `Monitor`, `Reactor` — это **не фэнтези**. Это следы sci-fi контента в фэнтези-игре: либо вырезанная локация, либо наследие движка DEEP6 от другого проекта.

Цепочка работы prop-объекта:
```
уровень (.bol) → placed object → prop id → D6PROP.DAT (архетип)
   → D6SWITxx/D6TRIGxx (состояние и условие в регионе)
   → EVENTS.COD (что произойдёт)
   → Granny модель по состоянию (*_opening / *_closing / *_TurnOn / *_TurnOff)
   → SFX через MONSOUND.DAT
```

---

## 12. Графика и звук

### 12.1. Granny 3D

4964 файла `.GR2`, 538 МБ. Именование кодирует состояние объекта:

| Шаблон | Смысл |
|---|---|
| `*_basemodel.GR2` | базовая модель/скелет |
| `*_opening.GR2` / `*_closing.GR2` | анимации открытия/закрытия |
| `*_readyopen.GR2` / `*_readyclosed.GR2` | idle-позы состояний |
| `*_On.GR2` / `*_Off.GR2` / `*_TurnOn.GR2` / `*_TurnOff.GR2` | активаторы |
| `*_Use.GR2` / `*_Activate.GR2` | использование |
| `AD_*` | архитектура Arindale |

Замена `.GR2` требует Granny-совместимого экспортёра (закрытое коммерческое SDK от RAD). Практически недоступно.

### 12.2. Текстуры

| Каталог | Файлов | Содержимое |
|---|---:|---|
| `interface/` | 1498 | UI, иконки (`ICONLIST.TXT` — индекс), курсоры `.ptr` |
| `CacheTex/` | 462 | кэш, 390 `.bmp` + 71 `.tga` |
| `MAINMENU/` | 142 | главное меню |
| `grn_texture/` | — | текстуры моделей (`pchm/PCHMTEX.TXT` — список текстур мужского PC) |
| `efxgfx/` | 80 | эффекты, `.al8`/`.al4` (палитровые) |
| `multigfx/` | 64 | мультиплеерный UI |
| `sprites/` | 42 | спрайты |
| `savegfx/` | 19 | миниатюры сейвов |
| `roadway/`, `sky/`, `WaterArt/`, `terrmap/` | 33 | окружение |

Форматы `.al8`, `.al4`, `.p16` — собственные палитровые/индексированные. Палитра — `DEEP6.PAL` (8960 байт).

### 12.3. Шейдеры

11 скомпилированных бинарников в `Shaders/`: `BasicShader.pso/.vso`, `BasicShader0/2/3`, `BasicShaderM.pso`, `BasicVertex0.vso`, `BumpWaveF.vso`, `BumpWaveFQ.vso`, `BumpWaveP.pso`, `BumpWavePQ.pso`.

Из `DEBUG.LOG`: `Vertex shader and pixel shader versions: FFFE0200, FFFF0200` → **Shader Model 2.0**.

`BumpWave*` — bump-mapping + волны, то есть вода. `Basic*` — базовые материалы. Исходников `.hlsl`/`.fx` нет.

### 12.4. Аудио и видео

| Слой | Ресурсы |
|---|---|
| SFX | `sounds/` — 661 `.wav`, 53 МБ; реестр `MONSOUND.DAT` |
| Музыка | `music/` — 1 `.mp3` (в этой установке; остальное на CD по `SSPATH.DAT`) |
| Речь | `speech.dat` — 1.01 ГБ, контейнер `SFFS`; `pctalk/TALKPAK.000..009` — индексы реплик PC |
| Видео | `bink_video/` — 6 `.bik`, 162 МБ |
| Драйверы Miles | `MilesRD/` — 6 `.m3d` (3D-аудио), 2 `.asi` (кодеки), 1 `.flt` (фильтр) |

`SSPATH.DAT` показывает, что игра рассчитана на чтение части медиа с CD:
```
CD-ROM G:/
NARRATOR SPEECH/
SPEECH SPEECH/
MUSIC MUSIC/
MOVIE MOVIE/
```
В `DEBUG.LOG` есть `CDROMMediaCheck()`. Установка полная (speech.dat локально), но проверка носителя в коде присутствует.

### 12.5. Контейнер `SFFS`

Три файла имеют одинаковый заголовок: `53 46 46 53` (`SFFS`) + `uint32 version = 1`, далее данные с высокой энтропией (сжато или зашифровано):

| Файл | Размер |
|---|---:|
| `speech.dat` | 1 088 675 888 |
| `root.dat` | 710 752 |
| `compass.dat` | 154 760 |

Не декодирован. Без разбора кода загрузчика в `dlords.exe` содержимое недоступно.

---

## 13. Интерфейс и управление

Экраны (из мануала): character (`C`), equipment/inventory (`E`), quick menu (`F`), journal/current tasks (`L`), взаимодействие (`Shift`), смена оружия (`Q`), воскрешение (`R`), сетевой чат (`Enter`).

Базовое управление: `WASD` — движение, `Space` — прыжок, ЛКМ — атака/каст, ПКМ — блок щитом.

HUD: портрет, красная полоса здоровья, синяя полоса прогресса уровня.

Данные UI: иконки в `interface/icons/*.bmp` (индекс `ICONLIST.TXT`), тексты в `rd6string.dat` (5000+ и 7000+), шрифты `*.FNT` (22 файла) + `DAKFNT16.INF`. Логика UI зашита в `dlords.exe`.

---

## 14. Безопасность

**Обнаружено при анализе:**

- `trivium.dll` — удалён/помещён в карантин Windows Defender как `VirTool:Win32/VMProtect`.
- `protect.exe` (7.6 МБ) и `protect.dll` (303 КБ) перемещены в `_local_quarantine_do_not_run/` и на месте остаются.

**Статус Defender:** `DidThreatExecute=False`, `IsActive=False`. Угроза не исполнялась.

**Оценка.** `VMProtect` — легальный коммерческий протектор кода; в играх 2004–2005 годов он применялся как DRM. Antivirus-эвристика помечает его сама по себе, независимо от полезной нагрузки. Это **не доказательство вредоносности**, но и не оправдание для запуска: под протектором нельзя проверить, что именно выполняется.

**Что было сделано:** созданы `PLAY_SAFE.ps1` (сканирование Defender + запуск `dlords.exe`), `RESTORE_PROTECT.ps1` (восстановление файлов), заметки перенесены в `documentation/legacy_reports/SAFE_PLAY_NOTES.txt`. Правила брандмауэра создать не удалось — Windows вернул `Access is denied` (нужен запуск от администратора).

**Что нужно для честной динамической проверки:**

1. Отдельная Windows-VM без доступа к личным файлам и сетевым дискам.
2. Snapshot до запуска.
3. Сеть отключена или firewall deny-all (напомню: игра штатно использует UDP 2606).
4. ProcMon — файлы, реестр, процессы.
5. TCPView / Wireshark — сетевая активность.
6. Сравнение снимка ФС и реестра до/после.
7. Проверка, требуются ли `protect.*` для легитимной работы. Если игра запускается без них — восстанавливать не нужно.

**Текущий отчёт построен на статическом анализе.** Ни один исполняемый файл игры не запускался.

---

## 15. Модификация: карта рисков

### Зелёная зона — правится текстом, откат тривиален

| Что | Файл | Комментарий |
|---|---|---|
| Реестр звуков | `MONSOUND.DAT` | plain text, комментарии, 742 слота |
| Правила дорог/мостов | `ROADBRID.DAT` | plain text |
| Биндинги и читы | `*.kbd` | plain text; читы уже включены |
| Пути к медиа | `SSPATH.DAT` | plain text |
| Иконки, UI, текстуры | `interface/`, `MAINMENU/`, `grn_texture/`, `terrtex_*` | сохранять размер, формат, палитру, альфу |
| Звуковые файлы | `sounds/*.wav` | сохранять кодек и частоту |

### Жёлтая зона — бинарно, но структура известна; нужен бэкап

| Что | Файл | Риск |
|---|---|---|
| Лут-листы и ассортимент магазинов | `D6TRLIST.DAT` | низкий: 18 × uint16 в фиксированной записи |
| Строки и имена | `rd6string.dat`, `iname.dat`, `mname.dat`, `pname.dat` | средний: сохранять CP1251 и пересчитывать offset-таблицу |
| Наборы звуков монстров | `D6MONSND.DAT` | низкий |
| Сокровища | `D6TREAS.DAT` | средний: семантика слотов не финальная |
| Скрипты NPC и квестов | `npccode/CODEFILE.*` | **средний** — текст читаем, но контейнер требует пересчёта `[tag][len]`; `tag` используется для `goto`, ломать его нельзя |

### Красная зона — не трогать без инструментов и рантайм-проверки

| Что | Почему |
|---|---|
| `D6ITEM.DAT`, `D6MONS.DAT`, `D6PROP.DAT` | семантика полей не подтверждена; количество записей вероятно зашито в exe |
| `EVENTS.COD` | байткод, опкоды неизвестны |
| Уровни (`.bsp`, `.twd`, `.lf`, `.bol`, …) | форматы закрыты |
| `TERRDATA.*` | форматы закрыты, 215 МБ |
| `speech.dat`, `root.dat`, `compass.dat` | контейнер `SFFS` не декодирован |
| `.GR2` | нужен коммерческий Granny SDK |
| Патч `dlords.exe` | ломает целостность и, вероятно, `protect` |
| Добавление новых записей в любую `D6*.DAT` | count-маркеры и лимиты в exe |

### Обязательный порядок работ

1. Полная копия каталога + манифест хешей (SHA-256).
2. Один файл за раз, одно изменение за раз.
3. Проверка запуском в VM.
4. Откат при первой аномалии.

---

## 16. Что лежит в этой папке

```
documentation/
├── DUNGEON_LORDS_FULL_REPORT.md      ← этот отчёт
├── extracted/                        новые данные (extract_v3.py)
│   ├── npc_scripts/npc_001..158.txt  расшифрованные скрипты NPC/квестов
│   ├── npc_script_index.csv          158 NPC: имя, квесты, темы диалогов
│   ├── npc_script_statements.csv     90 операторов языка скриптов
│   ├── quest_registers.csv           79 квестовых регистров
│   ├── dialogue_topics.csv           112 тем диалогов
│   ├── class_advancement.csv         96 переходов класс/ступень
│   ├── event_primitives.csv          182 примитива событий + описания
│   ├── event_param_stream.csv        1013 параметров событий
│   ├── sound_registry.csv            742 слота SFX
│   ├── monster_soundsets.csv         120 наборов звуков монстров
│   ├── console_bindings.csv          55 консольных команд
│   └── region_files.csv              384 региональных файла
├── research_export/                  данные первого этапа (20 файлов)
│   ├── items_raw.csv, item_names.csv, items_catalog.csv
│   ├── monsters_raw.csv, monster_names.csv, monster_loot_candidates.csv
│   ├── npcs_raw.csv, props_raw.csv, prop_names.csv
│   ├── strings_rd6.csv, manual_spells.csv, manual_text.json
│   ├── treasure_lists_u16.csv, treasure_entries_decoded.csv, …
│   └── region_data_inventory.csv, summary.json
├── tools/
│   ├── extract_v3.py                 новый экстрактор
│   ├── tools_extract_data.py         базовый (этап 1)
│   ├── tools_extract_loot_events.py  устарел, ошибка парсинга switch
│   └── tools_extract_loot_events_v2.py
└── legacy_reports/                   предыдущие отчёты, как есть
    ├── FULL_GAME_TECH_REVIEW.md
    ├── RESEARCH_SUMMARY.md
    ├── LOOT_EVENTS_RESEARCH.md
    ├── research_export_README.md
    └── SAFE_PLAY_NOTES.txt
```

Перезапуск экстрактора (из корня игры):
```powershell
python documentation\tools\extract_v3.py
```

---

## 17. Открытые вопросы

Отсортировано по соотношению ценность / трудозатраты.

| # | Задача | Ценность | Сложность | Подход |
|---|---|---|---|---|
| 1 | Мост `iname.dat` ↔ `D6ITEM.DAT` | 🔴 критично | средняя | искать в `D6ITEM.DAT` поле, чьё распределение совпадает с id из `iname.dat`; либо трассировать `MakeITEMS()` в отладчике |
| 2 | Обратная сборка `CODEFILE` (текст → контейнер) | 🔴 критично | низкая | формат известен; нужен корректный пересчёт `tag` для `goto` |
| 3 | Схема записи `D6TRIGxx` | 🟠 высокая | средняя | записи переменной длины; вывести по count и наличию вложенных списков |
| 4 | Опкоды `EVENTS.COD` | 🟠 высокая | высокая | 182 точки входа известны; средняя длина 42 Б → перебор коротких паттернов реален |
| 5 | Подтвердить дроп монстров (`u16_334`) | 🟠 высокая | низкая (нужен запуск) | контролируемый тест в VM |
| 6 | Требования классов: Agility/Vitality/уровень/навыки | 🟡 средняя | низкая | `Manual/HTML/AppendixB.htm` |
| 7 | Формат сейва `D6SEGnn.GAM` | 🟡 средняя | средняя | сейвов в установке нет — создать в VM и сравнить |
| 8 | Контейнер `SFFS` | 🟡 средняя | высокая | реверс загрузчика в `dlords.exe` |
| 9 | `D6WORLD.DAT`, `D6HELM.DAT` | 🟢 низкая | средняя | сопоставить с сеткой сегментов и списком шлемов |
| 10 | Формат `.bol` (размещение объектов) | 🟢 низкая | высокая | нужен для просмотрщика карт |
| 11 | `TERRDATA.*` | 🟢 низкая | очень высокая | 215 МБ, закрытый формат |

---

## 18. Итоговая оценка

**Что это.** Legacy action-RPG 2004 года на закрытом собственном движке DEEP6 (Heuristic Park), с Granny 3D, Bink, Miles и Direct3D 9 / Shader Model 2.0. Русская локализация 1С/Nival, версия 1.5 Collector's Edition. Установка полная, 2.88 ГБ, 10 791 файл.

**Насколько открыт.** Гораздо больше, чем предполагали предыдущие отчёты. Три ключевых слоя оказались текстовыми и полностью читаемыми:

- квесты и диалоги (`npccode/`, 158 скриптов, 1.5 МБ),
- декларации мировых событий (`EVENTS.DCL`, 182 примитива с описаниями),
- реестр звуков (`MONSOUND.DAT`, 742 слота).

Плюс табличный слой (предметы, монстры, лут, строки, props) со стабильной и уже расшифрованной структурой записей.

**Что закрыто.** Геометрия уровней, глобальный ландшафт, контейнеры `SFFS`, байткод событий, Granny-ассеты, сам `dlords.exe`.

**Практический вывод.** Игра пригодна для содержательного моддинга без патча исполняемого файла:

- ✅ баланс лута и ассортимента магазинов — `D6TRLIST.DAT`
- ✅ звуковой дизайн — `MONSOUND.DAT` + `sounds/`
- ✅ визуальный рескин UI и текстур
- ✅ тексты, имена, реплики
- ✅ квестовая логика и диалоги — после того, как будет написан обратный упаковщик `CODEFILE`
- ❌ новые уровни, новые модели, новые записи в таблицах

**Главный технический milestone** — обратный упаковщик `npccode/CODEFILE.*`. Формат контейнера тривиален, работа небольшая, а результат открывает полный контроль над квестами, диалогами, наградами, поведением NPC и условиями получения классов. Это единственный пункт, который переводит проект из «читаем» в «редактируем».

**Главный риск** — запуск неизвестного `protect.*`/`trivium.dll` вне изолированной среды. До завершения проверки в VM запуск игры на рабочей машине не оправдан.
