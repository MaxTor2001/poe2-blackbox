"""Parse waystone text copied from the game and watch the clipboard for it."""

import re
import threading
import time
from datetime import datetime
from pathlib import Path

import pyperclip

from blackbox.log_lines import Event
from blackbox.store import Store

TIER = re.compile(r"Waystone \(Tier (\d+)\)")
RANGE = re.compile(r"\((?:\d+(?:\.\d+)?)-(?:\d+(?:\.\d+)?)\)")


def parse_waystone(text: str) -> dict | None:
    """Return {"name", "tier", "mods"} for waystone item text, else None."""
    sections = [s.strip().splitlines() for s in text.replace("\r", "").split("--------")]
    header = sections[0]
    if not header or header[0] != "Item Class: Waystones":
        return None
    tier_line = next((line for line in header if TIER.search(line)), "")
    name = header[2] if len(header) > 3 else tier_line
    mods = _mods_section(sections)
    return {"name": name, "tier": int(TIER.search(tier_line).group(1)), "mods": mods}


def _mods_section(sections: list[list[str]]) -> list[str]:
    for i, section in enumerate(sections[:-1]):
        if any(line.startswith("Item Level:") for line in section):
            return [_clean(line) for line in sections[i + 1] if not line.startswith("{")]
    return []


def _clean(line: str) -> str:
    return RANGE.sub("", line.split(" — ")[0]).strip()


class ClipboardWatcher(threading.Thread):
    """Poll the clipboard and record every waystone copied from the game."""

    def __init__(self, db: Path, paste=pyperclip.paste, interval: float = 0.5):
        super().__init__(daemon=True)
        self.db, self.paste, self.interval = db, paste, interval

    def run(self):
        store = Store(self.db)
        last = None
        while True:
            try:
                text = self.paste()
            except pyperclip.PyperclipException:
                text = None
            if text and text != last:
                last = text
                data = parse_waystone(text)
                if data:
                    store.add(Event(datetime.now().replace(microsecond=0), "waystone", data))
            time.sleep(self.interval)
