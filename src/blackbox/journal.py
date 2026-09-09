"""Build death records with context from the raw event stream."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from blackbox.log_lines import Event


@dataclass
class Death:
    ts: datetime
    character: str
    klass: str | None
    char_level: int | None
    zone: str | None
    area_level: int | None
    time_in_zone: timedelta | None


def deaths(events: list[Event]) -> list[Death]:
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
            result.append(Death(e.ts, e.data["character"], klass, level, zone, area_level, in_zone))
    return result
