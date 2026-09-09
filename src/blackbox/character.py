"""Fetch a character snapshot from the pathofexile.com character window."""

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from blackbox.store import Store

BASE = "https://www.pathofexile.com/character-window/"
USER_AGENT = "blackbox/0.1 (+https://github.com/itguy/poe2-blackbox)"
MIN_INTERVAL = 60.0


class Forbidden(Exception):
    """The site refused: these endpoints need a logged-in session (POESESSID)."""


def _get(path: str, params: dict, sessid: str | None) -> dict | list:
    url = BASE + path + "?" + urllib.parse.urlencode({"realm": "poe2", **params})
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    if sessid:
        req.add_header("Cookie", f"POESESSID={sessid}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as err:
        if err.code in (401, 403):
            raise Forbidden("pathofexile.com refused the request: set POESESSID (see README)") from None
        raise


def name_forms(account: str) -> list[str]:
    """`Name#1234` and `Name-1234` both occur in the wild; try the given form first."""
    other = account.replace("#", "-") if "#" in account else account.replace("-", "#") if "-" in account else None
    return [account] + ([other] if other else [])


def fetch_snapshot(account: str, sessid: str | None = None, character: str | None = None) -> dict:
    """Snapshot `character` (the one you are playing, known from the log); else the site's best guess."""
    chars, used = None, account
    for form in name_forms(account):
        try:
            chars, used = _get("get-characters", {"accountName": form}, sessid), form
            break
        except urllib.error.HTTPError as err:
            if err.code != 404:
                raise
    if not chars:
        raise RuntimeError(f"no characters found for account {account!r}")
    meta = _pick(chars, character)
    name = meta["name"]
    items = _get("get-items", {"accountName": used, "character": name}, sessid)
    passives = _get("get-passive-skills", {"accountName": used, "character": name}, sessid)
    return {"character": meta, "items": items.get("items", []), "passives": passives}


def _pick(chars: list[dict], character: str | None) -> dict:
    if character:
        match = next((c for c in chars if c.get("name") == character), None)
        if match:
            return match
    return next((c for c in chars if c.get("lastActive")), chars[-1])


class Snapshotter(threading.Thread):
    """Takes a snapshot on demand, at most once per MIN_INTERVAL, without blocking the caller."""

    def __init__(self, db: Path, account: str, sessid: str | None, fetch=fetch_snapshot):
        super().__init__(daemon=True)
        self.db, self.account, self.sessid, self.fetch = db, account, sessid, fetch
        self.wanted = threading.Event()
        self.last_taken = 0.0
        self.current: str | None = None  # character you are playing, set from the log

    def request(self, character: str | None = None) -> None:
        if character:
            self.current = character
        self.wanted.set()

    def run(self):
        store = Store(self.db)
        while True:
            self.wanted.wait()
            self.wanted.clear()
            if time.monotonic() - self.last_taken < MIN_INTERVAL:
                continue
            try:
                snap = self.fetch(self.account, self.sessid, self.current)
            except Forbidden as err:
                print(f"gear snapshots disabled: {err}")
                return
            except Exception as err:  # network or API failure must not kill the watcher
                print(f"snapshot failed: {err!r}")
                continue
            self.last_taken = time.monotonic()
            store.add_snapshot(datetime.now(), snap["character"]["name"], snap)
            print(f"gear snapshot: {snap['character']['name']} lvl {snap['character'].get('level')}, {len(snap['items'])} items")
