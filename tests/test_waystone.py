import time
from datetime import datetime, timedelta
from pathlib import Path

from blackbox.journal import deaths
from blackbox.log_lines import Event
from blackbox.store import Store
from blackbox.waystone import ClipboardWatcher, parse_waystone

ADVANCED = (Path(__file__).parent / "fixtures/waystone_advanced.txt").read_text()
PLAIN = """Item Class: Waystones
Rarity: Magic
Shocking Waystone (Tier 5) of Splitting
--------
Pack Size: +12% (augmented)
--------
Item Level: 70
--------
Area has patches of Shocked Ground
Monsters fire 2 additional Projectiles
--------
Can be used in a Map Device, allowing you to enter a Map. Waystones can only be used once.
"""


def test_parse_advanced_copy():
    w = parse_waystone(ADVANCED)
    assert (w["name"], w["tier"]) == ("Desolate Route", 14)
    assert w["mods"] == [
        "Area has patches of Shocked Ground",
        "28% increased Monster Damage",
        "Monsters fire 2 additional Projectiles",
        "Monsters have 293% increased Critical Hit Chance",
        "+26% to Monster Critical Damage Bonus",
    ]


def test_parse_plain_magic_copy():
    w = parse_waystone(PLAIN)
    assert (w["name"], w["tier"]) == ("Shocking Waystone (Tier 5) of Splitting", 5)
    assert w["mods"] == ["Area has patches of Shocked Ground", "Monsters fire 2 additional Projectiles"]


def test_non_waystone_ignored():
    assert parse_waystone("Item Class: Quarterstaves\nRarity: Rare\nDoom Staff\n") is None
    assert parse_waystone("") is None


def test_clipboard_watcher_records_once_per_copy(tmp_path):
    clip = [ADVANCED]
    ClipboardWatcher(tmp_path / "t.sqlite", paste=lambda: clip[0], interval=0.02).start()
    time.sleep(0.15)
    assert len(Store(tmp_path / "t.sqlite").events("waystone")) == 1


def test_death_gets_waystone_copied_before_zone_entry():
    t = datetime(2026, 9, 9, 14, 0, 0)
    w = {"name": "Desolate Route", "tier": 14, "mods": ["x"]}
    events = [
        Event(t, "waystone", w),
        Event(t + timedelta(minutes=1), "area", {"level": 79, "area_id": "MapAugury", "seed": 1}),
        Event(t + timedelta(minutes=1), "zone", {"name": "Augury"}),
        Event(t + timedelta(minutes=2), "zone", {"name": "Act 2"}),  # act label flicker, ignored
        Event(t + timedelta(minutes=5), "death", {"character": "Z"}),
        Event(t + timedelta(minutes=30), "area", {"level": 1, "area_id": "Hideout", "seed": 1}),
        Event(t + timedelta(minutes=30), "zone", {"name": "Hideout"}),
        Event(t + timedelta(minutes=31), "death", {"character": "Z"}),
    ]
    first, second = deaths(events)
    assert first.waystone == w
    assert first.zone == "Augury"
    assert second.waystone is None
