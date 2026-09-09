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
    assert 2.5 <= duration(clip) <= 4.5


def test_save_without_segments_fails(tmp_path):
    with pytest.raises(RuntimeError):
        Recorder(tmp_path, pipeline=TESTSRC).save_replay()
