"""SQLite storage for parsed events."""

import json
import sqlite3
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
"""


class Store:
    """Append-only event log. Duplicate (ts, kind, data) rows are ignored."""

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
        return [Event(_parse_ts(ts), k, json.loads(d)) for ts, k, d in rows]


def _parse_ts(value: str):
    from datetime import datetime

    return datetime.fromisoformat(value)
