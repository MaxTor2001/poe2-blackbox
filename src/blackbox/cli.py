"""Command line entry points."""

from pathlib import Path

import click

from blackbox.log_lines import parse_line
from blackbox.store import Store
from blackbox.tail import default_log_path, follow, read_all

DB_OPTION = click.option("--db", type=Path, default=Path("blackbox.sqlite"), show_default=True)
LOG_OPTION = click.option("--log", "log_path", type=Path, default=None, help="Path to Client.txt")


def _resolve_log(log_path: Path | None) -> Path:
    path = log_path or default_log_path()
    if path is None or not path.exists():
        raise click.ClickException("Client.txt not found, pass --log PATH")
    return path


@click.group()
def cli():
    """Hardcore black box for Path of Exile 2."""


@cli.command("import")
@LOG_OPTION
@DB_OPTION
def import_log(log_path, db):
    """Parse an entire Client.txt into the database."""
    store = Store(db)
    added = 0
    for line in read_all(_resolve_log(log_path)):
        event = parse_line(line)
        if event and store.add(event):
            added += 1
    click.echo(f"imported {added} new events")


@cli.command()
@LOG_OPTION
@DB_OPTION
def watch(log_path, db):
    """Follow Client.txt and record events as they happen."""
    store = Store(db)
    path = _resolve_log(log_path)
    click.echo(f"watching {path}")
    for line in follow(path):
        event = parse_line(line)
        if event and store.add(event):
            click.echo(f"{event.ts:%Y-%m-%d %H:%M:%S}  {event.kind:9} {event.data}")


@cli.command()
@DB_OPTION
def deaths(db):
    """List recorded deaths with the zone each happened in."""
    zone = "?"
    level = "?"
    for event in Store(db).events():
        if event.kind == "zone":
            zone = event.data["name"]
        elif event.kind == "area":
            level = event.data["level"]
        elif event.kind == "death":
            click.echo(f"{event.ts:%Y-%m-%d %H:%M:%S}  {event.data['character']}  died in {zone} (area level {level})")
