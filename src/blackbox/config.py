"""Small persisted settings (account name, session cookie) in the user data folder."""

import json
import os
from pathlib import Path

from blackbox.paths import data_dir


def config_path() -> Path:
    return data_dir() / "config.json"


def load() -> dict:
    path = config_path()
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save(**values) -> dict:
    """Merge non-empty values into the config file and return the result."""
    current = load()
    current.update({k: v for k, v in values.items() if v})
    path = config_path()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)  # holds a session cookie: owner-only
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    return current
