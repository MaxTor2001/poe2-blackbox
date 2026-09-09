"""Follow Client.txt and yield new complete lines as they appear."""

import time
from collections.abc import Iterator
from pathlib import Path


def read_all(path: Path) -> Iterator[str]:
    """Yield every line of an existing log file."""
    with path.open(encoding="utf-8", errors="replace") as f:
        yield from f


def follow(path: Path, poll_seconds: float = 0.5) -> Iterator[str]:
    """Yield lines appended after this call; restart from zero if the file is truncated."""
    return _follow_from(path, path.stat().st_size, poll_seconds)


def _follow_from(path: Path, position: int, poll_seconds: float) -> Iterator[str]:
    buffer = ""
    while True:
        size = path.stat().st_size
        if size < position:
            position = 0
            buffer = ""
        if size == position:
            time.sleep(poll_seconds)
            continue
        with path.open("rb") as f:
            f.seek(position)
            chunk = f.read(size - position)
        position = size
        buffer += chunk.decode("utf-8", errors="replace")
        *complete, buffer = buffer.split("\n")
        yield from complete


def default_log_path() -> Path | None:
    """Guess Client.txt location for a Steam install on Linux."""
    home = Path.home()
    candidates = [
        home / ".steam/steam/steamapps/common/Path of Exile 2/logs/Client.txt",
        home / ".local/share/Steam/steamapps/common/Path of Exile 2/logs/Client.txt",
    ]
    return next((p for p in candidates if p.exists()), None)
