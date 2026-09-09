import time
from datetime import datetime, timedelta

from blackbox import character
from blackbox.character import Snapshotter
from blackbox.journal import latest_gear
from blackbox.store import Store

SNAP = {
    "character": {"name": "Zahrek", "level": 91, "class": "Monk"},
    "items": [{"inventoryId": "Weapon", "name": "Doom Staff", "typeLine": "Quarterstaff"}, {"inventoryId": "Helm", "name": "", "typeLine": "Iron Crown"}],
    "passives": {"hashes": [1, 2]},
}


def test_snapshotter_stores_and_throttles(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(character, "MIN_INTERVAL", 0.2)
    snapper = Snapshotter(tmp_path / "t.sqlite", "acct", None, fetch=lambda a, s, c: calls.append(c) or SNAP)
    snapper.current = "Zahrek"
    snapper.start()
    snapper.request()
    time.sleep(0.05)
    snapper.request()  # inside MIN_INTERVAL, skipped
    time.sleep(0.3)
    snapper.request()
    time.sleep(0.05)
    assert calls == ["Zahrek", "Zahrek"]
    snaps = Store(tmp_path / "t.sqlite").snapshots()
    assert [c for _, c, _ in snaps] == ["Zahrek", "Zahrek"]


def test_latest_gear_picks_closest_within_window():
    t = datetime(2026, 9, 9, 14, 5, 10)
    snaps = [(t - timedelta(minutes=25), "Zahrek", SNAP), (t + timedelta(seconds=30), "Zahrek", SNAP), (t - timedelta(minutes=1), "Other", SNAP)]
    gear = latest_gear(snaps, "Zahrek", t)  # death-time snapshot 30 s after is closest
    assert gear.taken_at == t + timedelta(seconds=30)
    assert gear.items == [("Weapon", "Doom Staff"), ("Helm", "Iron Crown")]
    assert latest_gear(snaps, "Nobody", t) is None
    far = [(t - timedelta(minutes=45), "Zahrek", SNAP), (t + timedelta(minutes=10), "Zahrek", SNAP)]
    assert latest_gear(far, "Zahrek", t) is None  # nothing inside the window


def test_pick_prefers_named_character():
    from blackbox.character import _pick

    chars = [{"name": "VendigosSSS", "level": 1}, {"name": "QuicklyDruid", "level": 5, "lastActive": True}]
    assert _pick(chars, "QuicklyDruid")["name"] == "QuicklyDruid"
    assert _pick([{"name": "A"}, {"name": "B"}], "Missing")["name"] == "B"  # fall back to last
    assert _pick(chars, None)["name"] == "QuicklyDruid"  # lastActive when no name given


def test_forced_request_bypasses_throttle(tmp_path, monkeypatch):
    import time as _t

    calls = []
    monkeypatch.setattr(character, "MIN_INTERVAL", 999)
    snapper = Snapshotter(tmp_path / "t.sqlite", "acct", None, fetch=lambda a, s, c: calls.append(c) or SNAP)
    snapper.start()
    snapper.request("QuicklyDruid")
    _t.sleep(0.1)
    snapper.request("QuicklyDruid", force=True)  # forced snapshot bypasses the throttle
    _t.sleep(0.1)
    assert calls == ["QuicklyDruid", "QuicklyDruid"]
