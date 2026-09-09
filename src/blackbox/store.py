"""SQLite storage for parsed events and ping samples."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from blackbox.log_lines import Event

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    kind TEXT NOT NULL,
    data TEXT NOT NULL,
    UNIQUE (ts, kind, data)
);
CREATE TABLE IF NOT EXISTS pings (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    host TEXT NOT NULL,
    rtt_ms REAL
);
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    character TEXT NOT NULL,
    data TEXT NOT NULL
);
"""


class Store:
    """Append-only log. Duplicate (ts, kind, data) events are ignored."""

    def __init__(self, path: Path):
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)

    def add(self, event: Event) -> bool:
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO events (ts, kind, data) VALUES (?, ?, ?)",
            (event.ts.isoformat(), event.kind, json.dumps(event.data, sort_keys=True)),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def events(self, kind: str | None = None) -> list[Event]:
        sql = "SELECT ts, kind, data FROM events"
        args: tuple = ()
        if kind:
            sql += " WHERE kind = ?"
            args = (kind,)
        rows = self.conn.execute(sql + " ORDER BY ts, id", args).fetchall()
        return [Event(datetime.fromisoformat(ts), k, json.loads(d)) for ts, k, d in rows]

    def add_ping(self, ts: datetime, host: str, rtt_ms: float | None) -> None:
        self.conn.execute("INSERT INTO pings (ts, host, rtt_ms) VALUES (?, ?, ?)", (ts.isoformat(), host, rtt_ms))
        self.conn.commit()

    def pings(self) -> list[tuple[datetime, float | None]]:
        rows = self.conn.execute("SELECT ts, rtt_ms FROM pings ORDER BY ts, id").fetchall()
        return [(datetime.fromisoformat(ts), rtt) for ts, rtt in rows]

    def add_snapshot(self, ts: datetime, character: str, data: dict) -> None:
        self.conn.execute(
            "INSERT INTO snapshots (ts, character, data) VALUES (?, ?, ?)",
            (ts.isoformat(), character, json.dumps(data)),
        )
        self.conn.commit()

    def snapshots(self) -> list[tuple[datetime, str, dict]]:
        rows = self.conn.execute("SELECT ts, character, data FROM snapshots ORDER BY ts, id").fetchall()
        return [(datetime.fromisoformat(ts), c, json.loads(d)) for ts, c, d in rows]
