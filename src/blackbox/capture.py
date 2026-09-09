"""Built-in screen recorder: ffmpeg writes a ring of short segments, a clip is the last minute."""

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SEGMENT_SECONDS = 10
KEEP_SEGMENTS = 8  # 80 s of history
CLIP_SECONDS = 60
ENCODERS = [("h264_nvenc", ["-preset", "p1"]), ("libx264", ["-preset", "ultrafast", "-tune", "zerolatency"])]


def screen_input() -> list[str]:
    """ffmpeg input arguments for the whole screen on this platform."""
    if sys.platform == "win32":
        return ["-f", "gdigrab", "-framerate", "30", "-i", "desktop"]
    return ["-f", "x11grab", "-framerate", "30", "-i", os.environ.get("DISPLAY", ":0")]


def pick_encoder() -> list[str]:
    """First encoder that can actually encode a frame on this machine."""
    for name, opts in ENCODERS:
        probe = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=64x64:rate=1", "-frames:v", "1", "-pix_fmt", "yuv420p", "-c:v", name, *opts, "-f", "null", "-"]
        if subprocess.run(probe, capture_output=True).returncode == 0:
            return ["-c:v", name, *opts]
    raise RuntimeError("no working h264 encoder in ffmpeg")


class Recorder:
    """Keeps the last ~80 s of screen in `work_dir`; `save_replay` writes the last minute as one file."""

    def __init__(self, work_dir: Path, input_args: list[str] | None = None, segment_seconds: int = SEGMENT_SECONDS):
        self.work_dir = work_dir
        self.input_args = input_args or screen_input()
        self.segment_seconds = segment_seconds
        self.process: subprocess.Popen | None = None

    def start(self) -> None:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        for old in self.work_dir.glob("seg*.ts"):
            old.unlink()
        cmd = [
            "ffmpeg", "-v", "error", "-y", *self.input_args,
            "-vf", "scale=-2:'min(1080,ih)'", "-pix_fmt", "yuv420p", *pick_encoder(), "-g", "30",
            "-f", "segment", "-segment_time", str(self.segment_seconds), "-segment_wrap", str(KEEP_SEGMENTS),
            "-reset_timestamps", "1", str(self.work_dir / "seg%02d.ts"),
        ]
        self.process = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stderr=(self.work_dir / "ffmpeg.log").open("ab"))

    def stop(self) -> None:
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=10)

    def save_replay(self) -> str:
        """Concatenate the segments touched within the last CLIP_SECONDS into one mp4."""
        cutoff = time.time() - CLIP_SECONDS - self.segment_seconds
        recent = sorted((p for p in self.work_dir.glob("seg*.ts") if p.stat().st_mtime >= cutoff), key=lambda p: p.stat().st_mtime)
        if not recent:
            raise RuntimeError("no recorded segments yet")
        out = self.work_dir / f"death-{datetime.now():%Y-%m-%d_%H-%M-%S}.mp4"
        concat = "concat:" + "|".join(str(p) for p in recent)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", concat, "-c", "copy", "-movflags", "+faststart", str(out)], check=True)
        return str(out)
