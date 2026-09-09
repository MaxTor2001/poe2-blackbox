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

HOSTS = [
    ("https://www.pathofexile.com/character-window/", {"realm": "poe2"}),
]
USER_AGENT = "blackbox/0.1 (+https://github.com/itguy/poe2-blackbox)"
MIN_INTERVAL = 60.0


class Forbidden(Exception):
    """The site refused: these endpoints need a logged-in session (POESESSID)."""


class WrongAccount(Exception):
    """The account returned characters that don't include the one you are playing."""


class Unavailable(Exception):
    """The endpoint returned something other than JSON (wrong host / no such API)."""


def _get(path: str, params: dict, sessid: str | None, base: str, realm: dict) -> dict | list:
    url = base + path + "?" + urllib.parse.urlencode({**realm, **params})
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    if sessid:
        req.add_header("Cookie", f"POESESSID={sessid}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()
    except urllib.error.HTTPError as err:
        if err.code in (401, 403):
            raise Forbidden("the site refused the request; the POESESSID may be stale") from None
        raise
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        raise Unavailable(f"{base} did not return JSON (no character API here)") from None


def name_forms(account: str) -> list[str]:
    """`Name#1234` and `Name-1234` both occur in the wild; try the given form first."""
    other = account.replace("#", "-") if "#" in account else account.replace("-", "#") if "-" in account else None
    return [account] + ([other] if other else [])


def _characters(query: dict, sessid: str | None, base: str, realm: dict) -> list[dict]:
    try:
        result = _get("get-characters", query, sessid, base, realm)
        return result if isinstance(result, list) else []
    except Unavailable:
        return []
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return []
        raise


def fetch_snapshot(account: str, sessid: str | None = None, character: str | None = None) -> dict:
    """Snapshot `character` (the one you are playing, known from the log).

    PoE2 characters live on pathofexile2.com; the legacy pathofexile.com endpoint returns PoE1
    characters even with realm=poe2. So try both hosts and only accept a list that contains
    `character`, in the session's own characters and both Name#1234 / Name-1234 account forms.
    """
    queries = ([{}] if sessid else []) + [{"accountName": form} for form in name_forms(account)]
    seen: list[str] = []
    for base, realm in HOSTS:
        for query in queries:
            chars = _characters(query, sessid, base, realm)
            seen += [c.get("name", "?") for c in chars]
            meta = _match(chars, character)
            if meta:
                used = query.get("accountName", account)
                name = meta["name"]
                items = _get("get-items", {"accountName": used, "character": name}, sessid, base, realm)
                passives = _get("get-passive-skills", {"accountName": used, "character": name}, sessid, base, realm)
                return {"character": meta, "items": items.get("items", []), "passives": passives}
    if character:
        raise WrongAccount(f"{character!r} not among characters the site returned for {account!r}: {sorted(set(seen)) or 'none'}")
    raise RuntimeError(f"no characters found for account {account!r}")


def _match(chars: list[dict], character: str | None) -> dict | None:
    if character:
        return next((c for c in chars if c.get("name") == character), None)
    return next((c for c in chars if c.get("lastActive")), chars[-1] if chars else None)


class Snapshotter(threading.Thread):
    """Takes a snapshot on demand, at most once per MIN_INTERVAL, without blocking the caller."""

    def __init__(self, db: Path, account: str, sessid: str | None, fetch=fetch_snapshot):
        super().__init__(daemon=True)
        self.db, self.account, self.sessid, self.fetch = db, account, sessid, fetch
        self.wanted = threading.Event()
        self.last_taken = 0.0
        self.current: str | None = None  # character you are playing, set from the log

        self.force = False

    def request(self, character: str | None = None, force: bool = False) -> None:
        if character:
            self.current = character
        if force:
            self.force = True
        self.wanted.set()

    def run(self):
        store = Store(self.db)
        while True:
            self.wanted.wait()
            self.wanted.clear()
            forced, self.force = self.force, False
            if not forced and time.monotonic() - self.last_taken < MIN_INTERVAL:
                continue
            try:
                snap = self.fetch(self.account, self.sessid, self.current)
            except Forbidden as err:
                print(f"gear snapshots disabled: {err}")
                return
            except WrongAccount as err:
                print(f"gear snapshots disabled: {err} (check --account)")
                return
            except Exception as err:  # network or API failure must not kill the watcher
                print(f"snapshot failed: {err!r}")
                continue
            self.last_taken = time.monotonic()
            store.add_snapshot(datetime.now(), snap["character"]["name"], snap)
            print(f"gear snapshot: {snap['character']['name']} lvl {snap['character'].get('level')}, {len(snap['items'])} items")
