"""Locate Client.txt and bundled binaries on each platform."""

import os
import shutil
import sys
from pathlib import Path


def default_log_path() -> Path | None:
    """First existing Client.txt among the usual Steam and standalone install locations."""
    return next((p for p in _log_candidates() if p.exists()), None)


def _log_candidates():
    tail = Path("steamapps/common/Path of Exile 2/logs/Client.txt")
    if sys.platform == "win32":
        pf = Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
        yield pf / "Steam" / tail
        yield pf / "Grinding Gear Games/Path of Exile 2/logs/Client.txt"
        for drive in "CDEF":
            yield Path(f"{drive}:/SteamLibrary") / tail
            yield Path(f"{drive}:/Games/SteamLibrary") / tail
    else:
        home = Path.home()
        yield home / ".steam/steam" / tail
        yield home / ".local/share/Steam" / tail


def data_dir() -> Path:
    """Per-user data folder for the database, clips and log; survives program updates."""
    from platformdirs import user_data_dir

    path = Path(user_data_dir("poe2-blackbox", appauthor=False))
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def ffmpeg(name: str = "ffmpeg") -> str:
    """Bundled ffmpeg/ffprobe next to the frozen executable, otherwise the one on PATH."""
    exe = name + (".exe" if sys.platform == "win32" else "")
    for base in (Path(sys.executable).parent, Path(getattr(sys, "_MEIPASS", ""))):
        if base and (base / exe).exists():
            return str(base / exe)
    return shutil.which(name) or name
