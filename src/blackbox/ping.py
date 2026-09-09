"""Measure round-trip time to the current instance server with plain TCP connects."""

import socket
import threading
import time
from datetime import datetime
from pathlib import Path

from blackbox.store import Store


def tcp_rtt(host: str, port: int, timeout: float = 2.0) -> float | None:
    """Milliseconds to open a TCP connection, or None on timeout/refusal."""
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError:
        return None
    return (time.perf_counter() - start) * 1000


class Pinger(threading.Thread):
    """Background thread probing `target` every `interval` seconds into its own Store."""

    def __init__(self, db: Path, interval: float = 2.0):
        super().__init__(daemon=True)
        self.db = db
        self.interval = interval
        self.target: tuple[str, int] | None = None

    def run(self):
        store = Store(self.db)
        while True:
            if self.target:
                host, port = self.target
                store.add_ping(datetime.now(), host, tcp_rtt(host, port))
            time.sleep(self.interval)
