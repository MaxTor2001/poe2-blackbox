"""Save the OBS replay buffer through obs-websocket (protocol v5)."""

import base64
import hashlib
import json
import threading
import time
from datetime import datetime
from pathlib import Path

from websockets.sync.client import connect

from blackbox.store import Store

CLIP_DELAY = 4.0  # seconds after death, so the death itself is in the clip


class Obs:
    """Minimal obs-websocket client: identify, then send requests."""

    def __init__(self, url: str = "ws://127.0.0.1:4455", password: str | None = None, settle: float = 1.5):
        self.url, self.password, self.settle = url, password, settle

    def request(self, request_type: str, data: dict | None = None) -> dict:
        with connect(self.url, proxy=None) as ws:  # OBS is local, never go through a proxy
            hello = json.loads(ws.recv())["d"]
            ws.send(json.dumps({"op": 1, "d": {"rpcVersion": 1, **self._auth(hello)}}))
            json.loads(ws.recv())  # Identified
            ws.send(json.dumps({"op": 6, "d": {"requestType": request_type, "requestId": "1", "requestData": data or {}}}))
            reply = json.loads(ws.recv())["d"]
        if not reply["requestStatus"]["result"]:
            raise RuntimeError(f"{request_type}: {reply['requestStatus'].get('comment')}")
        return reply.get("responseData", {})

    def _auth(self, hello: dict) -> dict:
        challenge = hello.get("authentication")
        if not challenge:
            return {}
        secret = base64.b64encode(hashlib.sha256((self.password or "").encode() + challenge["salt"].encode()).digest())
        answer = base64.b64encode(hashlib.sha256(secret + challenge["challenge"].encode()).digest())
        return {"authentication": answer.decode()}

    def ensure_replay_buffer(self) -> None:
        if not self.request("GetReplayBufferStatus")["outputActive"]:
            self.request("StartReplayBuffer")

    def save_replay(self) -> str:
        self.request("SaveReplayBuffer")
        time.sleep(self.settle)  # OBS needs a moment to write the file
        return self.request("GetLastReplayBufferReplay")["savedReplayPath"]


def follow_game(recorder, is_running, log, interval: float = 5.0) -> threading.Thread:
    """Start/stop `recorder` as the game window appears/disappears. No-op where presence is unknown."""

    def loop():
        while True:
            running = is_running()
            if running is None:
                return
            if running and not recorder.running:
                log("game started, recording")
                recorder.start()
            elif not running and recorder.running:
                log("game closed, recording paused")
                recorder.stop()
            time.sleep(interval)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    return thread


class Clipper:
    """Saves a replay clip a few seconds after each death and records its path.

    `backend` is anything with save_replay() -> path: Obs or capture.Recorder.
    """

    def __init__(self, db: Path, backend, delay: float = CLIP_DELAY):
        self.db, self.backend, self.delay = db, backend, delay

    def close(self) -> None:
        stop = getattr(self.backend, "stop", None)
        if stop:
            stop()

    def on_death(self, death_ts: datetime) -> None:
        threading.Thread(target=self._clip, args=(death_ts,), daemon=True).start()

    def _clip(self, death_ts: datetime) -> None:
        time.sleep(self.delay)
        try:
            path = self.backend.save_replay()
        except Exception as err:  # OBS may be closed; the journal must keep working
            print(f"clip failed: {err}")
            return
        Store(self.db).add_clip(death_ts, path)
