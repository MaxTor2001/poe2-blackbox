"""Build death records with context from the raw event stream."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from blackbox.log_lines import Event

PING_WINDOW = timedelta(seconds=60)
WAYSTONE_WINDOW = timedelta(minutes=15)


@dataclass
class PingSummary:
    avg_ms: float
    max_ms: float
    lost: int
    count: int


@dataclass
class Gear:
    taken_at: datetime
    level: int | None
    items: list[tuple[str, str]]  # (slot, display name)


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
    gear: Gear | None = None
    waystone: dict | None = None
    clip: str | None = None


def deaths(events: list[Event], pings=(), snapshots=(), clips: dict | None = None) -> list[Death]:
    """Replay events in order and attach the current context to every death."""
    zone = area_level = zone_since = None
    last_waystone = zone_waystone = None
    awaiting_name = False
    levels: dict[str, tuple[str, int]] = {}
    result = []
    for e in events:
        if e.kind == "waystone":
            last_waystone = e
        elif e.kind == "area":
            area_level, zone_since, zone, awaiting_name = e.data["level"], e.ts, None, True
            recent = last_waystone and e.ts - last_waystone.ts <= WAYSTONE_WINDOW
            zone_waystone = last_waystone.data if recent else None
        elif e.kind == "zone" and awaiting_name:
            # the game flips the scene name between the zone and its act label while loading;
            # only the first name after area generation is the zone
            zone, awaiting_name = e.data["name"], False
        elif e.kind == "level_up":
            levels[e.data["character"]] = (e.data["class"], e.data["level"])
        elif e.kind == "death":
            klass, level = levels.get(e.data["character"], (None, None))
            in_zone = e.ts - zone_since if zone_since else None
            ping = summarize_pings(pings, e.ts)
            gear = latest_gear(snapshots, e.data["character"], e.ts)
            clip = (clips or {}).get(e.ts)
            result.append(Death(e.ts, e.data["character"], klass, level, zone, area_level, in_zone, ping, gear, zone_waystone, clip))
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


def latest_gear(snapshots, character: str, before: datetime) -> Gear | None:
    """Most recent snapshot of `character` taken before `before`."""
    match = [(ts, d) for ts, c, d in snapshots if c == character and ts <= before]
    if not match:
        return None
    ts, data = match[-1]
    items = [(i.get("inventoryId", "?"), (i.get("name") or i.get("typeLine") or "?")) for i in data.get("items", [])]
    return Gear(ts, data.get("character", {}).get("level"), items)


def summary(records: list[Death]) -> dict:
    """Per-character and per-zone death counts for the journal header."""
    by_char: dict[str, dict] = {}
    by_zone: dict[str, int] = {}
    for d in records:
        c = by_char.setdefault(d.character, {"class": d.klass, "count": 0, "last": d.ts, "level": d.char_level})
        c["count"] += 1
        if d.ts >= c["last"]:
            c["last"], c["level"], c["class"] = d.ts, d.char_level, d.klass or c["class"]
        if d.zone:
            by_zone[d.zone] = by_zone.get(d.zone, 0) + 1
    zones = sorted(by_zone.items(), key=lambda kv: -kv[1])[:5]
    chars = sorted(by_char.items(), key=lambda kv: kv[1]["last"], reverse=True)
    return {"characters": chars, "zones": zones, "total": len(records)}
