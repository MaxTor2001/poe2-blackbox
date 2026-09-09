"""Parse single Client.txt lines into game events."""

import re
from dataclasses import dataclass, field
from datetime import datetime

TIMESTAMP = r"^(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})"
HEADER = r".*?\[(?:INFO|DEBUG) Client \d+\] "

PATTERNS = {
    "death": re.compile(TIMESTAMP + HEADER + r": (?P<character>.+?) (?:has been slain|была? повержена?)\.$"),
    "level_up": re.compile(
        TIMESTAMP + HEADER + r": (?P<character>.+?) \((?P<klass>[^)]+)\) (?:is now level (?P<level>\d+)|достигает (?P<level_ru>\d+) уровня)$"
    ),
    "area": re.compile(
        TIMESTAMP + HEADER + r'Generating level (?P<level>\d+) area "(?P<area_id>[^"]+)" with seed (?P<seed>\d+)$'
    ),
    "connect": re.compile(TIMESTAMP + HEADER + r"Connecting to instance server at (?P<host>[\d.]+):(?P<port>\d+)$"),
    "zone": re.compile(
        TIMESTAMP + HEADER + r"(?:: You have entered (?P<name_v1>.+?)\.|\[SCENE\] Set Source \[(?P<name_v2>[^\]]+)\])$"
    ),
}


@dataclass
class Event:
    """One parsed game event with its raw log timestamp."""

    ts: datetime
    kind: str
    data: dict = field(default_factory=dict)


def parse_line(line: str) -> Event | None:
    """Return an Event for a known line, or None for anything else."""
    line = line.rstrip()
    for kind, pattern in PATTERNS.items():
        m = pattern.match(line)
        if m:
            return _build(kind, m)
    return None


def _build(kind: str, m: re.Match) -> Event | None:
    ts = datetime.strptime(m.group(1), "%Y/%m/%d %H:%M:%S")
    g = m.groupdict()
    if kind == "zone":
        name = g["name_v1"] or g["name_v2"]
        if name.startswith("("):
            return None
        return Event(ts, kind, {"name": name})
    if kind == "area":
        return Event(ts, kind, {"level": int(g["level"]), "area_id": g["area_id"], "seed": int(g["seed"])})
    if kind == "connect":
        return Event(ts, kind, {"host": g["host"], "port": int(g["port"])})
    if kind == "level_up":
        return Event(ts, kind, {"character": g["character"], "class": g["klass"], "level": int(g["level"] or g["level_ru"])})
    return Event(ts, kind, {"character": g["character"]})
