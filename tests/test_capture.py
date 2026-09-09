import shutil
import subprocess
import time

import pytest

from blackbox.capture import Pipeline, Recorder, X264

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
TESTSRC = Pipeline("testsrc", ["-re", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30", *X264])  # -re: real-time pace


def duration(path: str) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True)
    return float(out.stdout)


def test_recorder_keeps_ring_and_saves_clip(tmp_path):
    rec = Recorder(tmp_path, pipeline=TESTSRC, segment_seconds=1)
    rec.start()
    try:
        time.sleep(3.5)
        clip = rec.save_replay()
    finally:
        rec.stop()
    assert clip.endswith(".mp4")
    assert 2.5 <= duration(clip) <= 6.5  # ~3.5 s wait + 1.5 s startup check


def test_save_without_segments_fails(tmp_path):
    with pytest.raises(RuntimeError):
        Recorder(tmp_path, pipeline=TESTSRC).save_replay()


def test_crop_filter_even_and_optional():
    from blackbox.capture import crop_filter

    assert crop_filter(None) == ""
    assert crop_filter((10, 20, 1281, 721)) == "crop=1280:720:10:20,"


def test_clamp_rect():
    from blackbox.gamewindow import clamp_rect

    assert clamp_rect((0, 0, 2560, 1440), 2560, 1440) is None  # whole screen: no crop needed
    assert clamp_rect((-100, 50, 1000, 800), 2560, 1440) == (0, 50, 900, 800)
    assert clamp_rect((2000, 1000, 1000, 800), 2560, 1440) == (2000, 1000, 560, 440)
    assert clamp_rect((10, 10, 40, 40), 2560, 1440) is None
    assert clamp_rect((100, 100, 1280, 720), 2560, 1440) == (100, 100, 1280, 720)


def test_launch_without_crop_when_crop_fails(tmp_path, monkeypatch):
    rec = Recorder(tmp_path, pipeline=TESTSRC, segment_seconds=1)
    monkeypatch.setattr(Recorder, "window_rect", staticmethod(lambda: (0, 0, 100, 100)))
    calls = []
    real = rec._launch

    def launch(rect):
        calls.append(rect)
        if rect:
            raise RuntimeError("bad crop")
        real(rect)

    monkeypatch.setattr(rec, "_launch", launch)
    rec.start()
    rec.stop()
    assert calls == [(0, 0, 100, 100), None]
