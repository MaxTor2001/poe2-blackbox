"""Command line entry points."""

import signal
import sys
from pathlib import Path

import click

from blackbox.capture import Recorder
from blackbox.character import Snapshotter
from blackbox.journal import deaths as build_deaths
from blackbox.obs import Clipper, Obs
from blackbox.log_lines import parse_line
from blackbox.ping import Pinger
from blackbox.store import Store
from blackbox.tail import default_log_path, follow, read_all
from blackbox.waystone import ClipboardWatcher

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
@click.option("--account", help="pathofexile.com account name; enables gear snapshots on zone entry")
@click.option("--sessid", envvar="POESESSID", help="POESESSID cookie for a private profile")
@click.option("--clips/--no-clips", default=True, show_default=True, help="Record the screen and save a clip on death")
@click.option("--obs", is_flag=True, help="Use OBS replay buffer instead of the built-in recorder")
@click.option("--obs-password", envvar="OBS_PASSWORD", help="obs-websocket password, if set")
def watch(log_path, db, account, sessid, clips, obs, obs_password):
    """Follow Client.txt, record events, probe ping and snapshot gear on zone entry."""
    store = Store(db)
    path = _resolve_log(log_path)
    pinger = Pinger(db)
    pinger.start()
    ClipboardWatcher(db).start()
    snapshotter = None
    if account:
        snapshotter = Snapshotter(db, account, sessid)
        snapshotter.start()
    clipper = None
    if clips:
        clipper = _connect_obs(db, obs_password) if obs else _start_recorder(db)
    click.echo(f"watching {path}")
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        for line in follow(path):
            event = parse_line(line)
            if not event:
                continue
            if event.kind == "connect":
                pinger.target = (event.data["host"], event.data["port"])
            if event.kind == "area" and snapshotter:
                snapshotter.request()
            if event.kind == "death" and clipper:
                clipper.on_death(event.ts)
            if store.add(event):
                click.echo(f"{event.ts:%Y-%m-%d %H:%M:%S}  {event.kind:9} {event.data}")
    finally:
        if clipper:
            clipper.close()


def _start_recorder(db) -> Clipper | None:
    recorder = Recorder(db.resolve().parent / "clips")
    try:
        recorder.start()
    except (OSError, RuntimeError) as err:
        click.echo(f"screen recording unavailable, clips disabled ({err})")
        return None
    click.echo(f"recording screen to {recorder.work_dir}")
    return Clipper(db, recorder)


def _connect_obs(db, password) -> Clipper | None:
    client = Obs(password=password)
    try:
        client.ensure_replay_buffer()
    except Exception as err:
        click.echo(f"OBS not available, clips disabled ({err.__class__.__name__})")
        return None
    click.echo("OBS replay buffer running, clips enabled")
    return Clipper(db, client)


@cli.command()
@DB_OPTION
def deaths(db):
    """List recorded deaths with the zone each happened in."""
    store = Store(db)
    for d in build_deaths(store.events(), store.pings(), store.snapshots(), store.clips()):
        tier = f" T{d.waystone['tier']}" if d.waystone else ""
        click.echo(f"{d.ts:%Y-%m-%d %H:%M:%S}  {d.character} lvl {d.char_level}  died in {d.zone}{tier} (area level {d.area_level})")


@cli.command()
@DB_OPTION
@click.option("--port", default=8765, show_default=True)
def serve(db, port):
    """Serve the death journal page on localhost."""
    import uvicorn

    from blackbox.web import create_app

    click.echo(f"death journal at http://127.0.0.1:{port}/")
    uvicorn.run(create_app(db), host="127.0.0.1", port=port, log_level="warning")
