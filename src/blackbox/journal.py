"""Build death records with context from the raw event stream."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from blackbox.log_lines import Event

PING_WINDOW = timedelta(seconds=60)


@dataclass
class PingSummary:
    avg_ms: float
    max_ms: float
    lost: int
    count: int


@dataclass
class Death:
    ts: datetime
    character: str
    klass: str | None
    char_level: int | None
    zone: str | None
    area_level: int | None
    time_in_zone: timedelta | None
    ping: PingSummary | None = None


def deaths(events: list[Event], pings: list[tuple[datetime, float | None]] = ()) -> list[Death]:
    """Replay events in order and attach the current context to every death."""
    zone = area_level = zone_since = None
    levels: dict[str, tuple[str, int]] = {}
    result = []
    for e in events:
        if e.kind == "zone":
            zone, zone_since = e.data["name"], e.ts
        elif e.kind == "area":
            area_level = e.data["level"]
        elif e.kind == "level_up":
            levels[e.data["character"]] = (e.data["class"], e.data["level"])
        elif e.kind == "death":
            klass, level = levels.get(e.data["character"], (None, None))
            in_zone = e.ts - zone_since if zone_since else None
            ping = summarize_pings(pings, e.ts)
            result.append(Death(e.ts, e.data["character"], klass, level, zone, area_level, in_zone, ping))
    return result


def summarize_pings(pings, until: datetime) -> PingSummary | None:
    """Summarize samples in the minute before `until`."""
    window = [rtt for ts, rtt in pings if until - PING_WINDOW <= ts <= until]
    if not window:
        return None
    ok = [r for r in window if r is not None]
    if not ok:
        return PingSummary(0, 0, len(window), len(window))
    return PingSummary(sum(ok) / len(ok), max(ok), len(window) - len(ok), len(window))
