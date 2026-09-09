import time

from blackbox.obs import follow_game


class FakeRecorder:
    def __init__(self):
        self.running = False
        self.log = []

    def start(self):
        self.running = True
        self.log.append("start")

    def stop(self):
        self.running = False
        self.log.append("stop")


def test_recorder_follows_game_window():
    state = {"running": False}
    rec = FakeRecorder()
    follow_game(rec, lambda: state["running"], lambda m: None, interval=0.02)
    time.sleep(0.05)
    assert rec.log == []
    state["running"] = True
    time.sleep(0.05)
    state["running"] = False
    time.sleep(0.05)
    assert rec.log == ["start", "stop"]


def test_unknown_presence_leaves_recorder_alone():
    rec = FakeRecorder()
    t = follow_game(rec, lambda: None, lambda m: None, interval=0.02)
    t.join(0.2)
    assert rec.log == [] and not t.is_alive()
