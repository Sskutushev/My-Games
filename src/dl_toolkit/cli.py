"""Командная строка ``dl``."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from dl_toolkit import __version__
from dl_toolkit.content import ClassTier, load_ruleset
from dl_toolkit.game import GameNotFoundError, GameRoot
from dl_toolkit.verify import summarize, verify_all

app = typer.Typer(
    name="dl",
    help="Инструменты реверс-инжиниринга и моддинга движка DEEP6.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()

GameOption = Annotated[
    Path | None,
    typer.Option("--game", "-g", help="Корень установки игры (иначе DL_GAME_ROOT или CWD)."),
]


def _root(game: Path | None) -> GameRoot:
    try:
        return GameRoot.discover(game)
    except GameNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc


@app.command()
def version() -> None:
    """Показать версию тулкита."""
    console.print(f"dl-toolkit {__version__}")


@app.command()
def verify(
    game: GameOption = None,
    scripts: Annotated[
        int | None, typer.Option("--scripts", help="Ограничить число проверяемых CODEFILE.")
    ] = None,
) -> None:
    """Проверить round-trip всех поддерживаемых форматов установки.

    Провал означает, что кодек нельзя использовать для записи в игру.
    """
    root = _root(game)
    results = verify_all(root, script_limit=scripts)
    ok, total = summarize(results)

    failures = [r for r in results if not r.ok]
    if failures:
        table = Table(title="Расхождения round-trip")
        table.add_column("файл")
        table.add_column("кодек")
        table.add_column("байт", justify="right")
        table.add_column("детали")
        for result in failures:
            table.add_row(result.file, result.codec, str(result.size), result.detail)
        console.print(table)

    style = "green" if ok == total else "red"
    console.print(f"[{style}]round-trip: {ok}/{total}[/{style}]")
    if ok != total:
        raise typer.Exit(code=1)


@app.command()
def capacity(game: GameOption = None) -> None:
    """Показать свободную ёмкость таблиц: сколько контента вообще можно добавить."""
    from dl_toolkit.codecs import LootListCodec, StringTableCodec
    from dl_toolkit.schema import FIXED_TABLES, REGION_GROUPS, REGION_SLOTS, STRING_TABLES

    root = _root(game)

    table = Table(title="Ёмкость таблиц фиксированных записей")
    table.add_column("файл")
    table.add_column("записей", justify="right")
    table.add_column("счётчик", justify="right")
    table.add_column("свободно", justify="right")
    for spec in FIXED_TABLES:
        fixed = spec.codec().decode(root.read(spec.filename))
        table.add_row(
            spec.filename,
            str(len(fixed)),
            str(fixed.declared_count),
            str(len(fixed.free_slots())),
        )
    console.print(table)

    string_codec = StringTableCodec()
    strings = Table(title="Строковые таблицы")
    strings.add_column("файл")
    strings.add_column("строк", justify="right")
    strings.add_column("макс. id", justify="right")
    for filename in STRING_TABLES:
        table_model = string_codec.decode(root.read(filename))
        ids = [sid for sid, _ in table_model.entries]
        strings.add_row(filename, str(len(table_model)), str(max(ids) if ids else 0))
    console.print(strings)

    loot = LootListCodec().decode(root.read("D6TRLIST.DAT"))
    console.print(
        f"D6TRLIST.DAT: списков {len(loot.lists)}, свободных слотов под предметы "
        f"{loot.free_capacity()}, полностью пустых списков {len(loot.empty_lists())}"
    )

    regions = Table(title="Региональные слоты")
    regions.add_column("группа")
    regions.add_column("занято", justify="right")
    regions.add_column("свободно", justify="right")
    for group, label in REGION_GROUPS.items():
        used = sum(1 for path in root.glob(f"D6{group}??.DAT") if path.stat().st_size > 4)
        regions.add_row(f"{group} — {label}", str(used), str(REGION_SLOTS - used))
    console.print(regions)


@app.command()
def rules(
    path: Annotated[Path, typer.Argument(help="YAML со сводом правил.")],
    matrix: Annotated[bool, typer.Option("--matrix", help="Вывести матрицу навыков.")] = False,
) -> None:
    """Провалидировать свод правил новой игры и показать сводку."""
    ruleset = load_ruleset(path)
    console.print(f"[bold]{ruleset.title_ru}[/bold] ({ruleset.title_en})")
    console.print(
        f"расы: {len(ruleset.playable_races())} играбельных из {len(ruleset.races)} слотов · "
        f"классы: {len(ruleset.classes)} · навыки: {len(ruleset.skills)} · "
        f"максимальный уровень: {ruleset.progression.max_level}"
    )

    tiers = Table(title="Классы по ступеням")
    tiers.add_column("ступень")
    tiers.add_column("кол-во", justify="right")
    tiers.add_column("классы")
    for tier in ClassTier:
        members = ruleset.classes_by_tier(tier)
        if members:
            tiers.add_row(tier.value, str(len(members)), ", ".join(c.name_ru for c in members))
    console.print(tiers)

    if matrix:
        grid = Table(title="Пределы навыков по классам")
        grid.add_column("класс")
        grid.add_column("навыки (предел)")
        for class_key, caps in ruleset.skill_matrix().items():
            top = sorted(caps.items(), key=lambda kv: -kv[1])[:8]
            grid.add_row(class_key, ", ".join(f"{k}:{v}" for k, v in top))
        console.print(grid)


@app.command()
def migrate(
    path: Annotated[Path, typer.Argument(help="YAML со сводом правил.")],
    write: Annotated[
        bool, typer.Option("--write", help="Записать результат обратно в файл.")
    ] = False,
) -> None:
    """Привести файл дизайна к текущей версии схемы."""
    import yaml

    from dl_toolkit.migrations import migrate_document, pending

    document = yaml.safe_load(path.read_text("utf-8"))
    steps = pending(document)
    if not steps:
        console.print("[green]миграции не требуются[/green]")
        return
    console.print(f"применяю миграции: {' -> '.join(str(s) for s in [*steps, steps[-1] + 1])}")
    updated = migrate_document(document)
    if write:
        path.write_text(
            yaml.safe_dump(updated, allow_unicode=True, sort_keys=False, width=100), "utf-8"
        )
        console.print(f"[green]записано: {path}[/green]")
    else:
        console.print("[yellow]сухой прогон; повторите с --write[/yellow]")


@app.command()
def restore(
    file: Annotated[str, typer.Argument(help="Относительный путь файла игры.")],
    game: GameOption = None,
) -> None:
    """Вернуть файл игры из резервной копии."""
    root = _root(game)
    root.restore(file)
    console.print(f"[green]восстановлено из резервной копии: {file}[/green]")


if __name__ == "__main__":  # pragma: no cover
    app()
