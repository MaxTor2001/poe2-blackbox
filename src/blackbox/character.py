"""Fetch a character snapshot from the pathofexile.com character window."""

import json
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from blackbox.store import Store

BASE = "https://www.pathofexile.com/character-window/"
USER_AGENT = "blackbox/0.1 (+https://github.com/itguy/poe2-blackbox)"
MIN_INTERVAL = 60.0


def _get(path: str, params: dict, sessid: str | None) -> dict | list:
    url = BASE + path + "?" + urllib.parse.urlencode({"realm": "poe2", **params})
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    if sessid:
        req.add_header("Cookie", f"POESESSID={sessid}")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def fetch_snapshot(account: str, sessid: str | None = None) -> dict:
    """Return the last active character with its items and passives."""
    chars = _get("get-characters", {"accountName": account}, sessid)
    current = next((c for c in chars if c.get("lastActive")), chars[-1])
    name = current["name"]
    items = _get("get-items", {"accountName": account, "character": name}, sessid)
    passives = _get("get-passive-skills", {"accountName": account, "character": name}, sessid)
    return {"character": current, "items": items.get("items", []), "passives": passives}


class Snapshotter(threading.Thread):
    """Takes a snapshot on demand, at most once per MIN_INTERVAL, without blocking the caller."""

    def __init__(self, db: Path, account: str, sessid: str | None, fetch=fetch_snapshot):
        super().__init__(daemon=True)
        self.db, self.account, self.sessid, self.fetch = db, account, sessid, fetch
        self.wanted = threading.Event()
        self.last_taken = 0.0

    def request(self) -> None:
        self.wanted.set()

    def run(self):
        store = Store(self.db)
        while True:
            self.wanted.wait()
            self.wanted.clear()
            if time.monotonic() - self.last_taken < MIN_INTERVAL:
                continue
            try:
                snap = self.fetch(self.account, self.sessid)
            except Exception as err:  # network or API failure must not kill the watcher
                print(f"snapshot failed: {err}")
                continue
            self.last_taken = time.monotonic()
            store.add_snapshot(datetime.now(), snap["character"]["name"], snap)
