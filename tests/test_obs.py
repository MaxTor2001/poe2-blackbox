import json
import threading
import time
from datetime import datetime

from websockets.sync.server import serve

from blackbox.obs import Clipper, Obs
from blackbox.store import Store


class FakeObs:
    """Speaks just enough obs-websocket v5 to serve the requests we make."""

    def __init__(self, active=False):
        self.active, self.calls = active, []
        self.server = serve(self.handle, "127.0.0.1", 0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"ws://127.0.0.1:{self.server.socket.getsockname()[1]}"

    def handle(self, ws):
        ws.send(json.dumps({"op": 0, "d": {"rpcVersion": 1, "authentication": {"challenge": "c", "salt": "s"}}}))
        assert "authentication" in json.loads(ws.recv())["d"]
        ws.send(json.dumps({"op": 2, "d": {"negotiatedRpcVersion": 1}}))
        req = json.loads(ws.recv())["d"]
        self.calls.append(req["requestType"])
        data = {
            "GetReplayBufferStatus": {"outputActive": self.active},
            "StartReplayBuffer": {},
            "SaveReplayBuffer": {},
            "GetLastReplayBufferReplay": {"savedReplayPath": "/tmp/Replay.mkv"},
        }[req["requestType"]]
        ws.send(json.dumps({"op": 7, "d": {"requestType": req["requestType"], "requestId": req["requestId"], "requestStatus": {"result": True, "code": 100}, "responseData": data}}))


def test_ensure_replay_buffer_starts_when_inactive():
    fake = FakeObs(active=False)
    Obs(fake.url, password="pw").ensure_replay_buffer()
    assert fake.calls == ["GetReplayBufferStatus", "StartReplayBuffer"]


def test_clipper_saves_after_death(tmp_path):
    fake = FakeObs(active=True)
    ts = datetime(2026, 9, 9, 14, 5, 10)
    Clipper(tmp_path / "t.sqlite", Obs(fake.url, settle=0), delay=0).on_death(ts)
    time.sleep(0.3)
    assert fake.calls == ["SaveReplayBuffer", "GetLastReplayBufferReplay"]
    assert Store(tmp_path / "t.sqlite").clips() == {ts: "/tmp/Replay.mkv"}
