"""Built-in screen recorder: ffmpeg writes a ring of short segments, a clip is the last minute."""

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from blackbox.paths import ffmpeg

SEGMENT_SECONDS = 10
KEEP_SEGMENTS = 8  # 80 s of history
CLIP_SECONDS = 60
PROBE_FAILURES: dict[str, str] = {}
NO_WINDOW = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}  # ffmpeg must not pop a console


@dataclass
class Pipeline:
    """A complete capture+encode setup, cheapest variants first in `candidates()`."""

    name: str
    args: list[str]


NVENC = ["-c:v", "h264_nvenc", "-preset", "p1", "-tune", "ll", "-delay", "0", "-bf", "0", "-rc-lookahead", "0", "-b:v", "8M", "-g", "30"]
X264 = ["-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-g", "30"]


def candidates(monitor: int | None = None) -> list[Pipeline]:
    if sys.platform == "win32":
        dda = f"ddagrab=output_idx={monitor or 0}"
        return [
            Pipeline("ddagrab+nvenc (GPU only)", ["-init_hw_device", "d3d11va", "-filter_complex", f"{dda}:framerate=30", *NVENC]),
            Pipeline("ddagrab+nvenc 1080p", ["-init_hw_device", "d3d11va", "-filter_complex", f"{dda}:framerate=30,hwdownload,format=bgra,scale=-2:'min(1080,ih)'", "-pix_fmt", "yuv420p", *NVENC]),
            Pipeline("ddagrab+x264 720p", ["-init_hw_device", "d3d11va", "-filter_complex", f"{dda}:framerate=24,hwdownload,format=bgra,scale=-2:720", *X264]),
            Pipeline("gdigrab+x264 720p", ["-f", "gdigrab", "-framerate", "20", "-i", "desktop", "-vf", "scale=-2:720", *X264]),
        ]
    display = os.environ.get("DISPLAY", ":0")
    grab = ["-f", "x11grab", "-framerate", "30", "-i", display]
    return [
        Pipeline("x11grab+nvenc", [*grab, "-vf", "scale=-2:'min(1080,ih)'", "-pix_fmt", "yuv420p", *NVENC]),
        Pipeline("x11grab+x264 1080p", [*grab, "-vf", "scale=-2:'min(1080,ih)'", *X264]),
    ]


def pick_pipeline(monitor: int | None = None) -> Pipeline:
    """First pipeline that records two seconds on this machine; failures are kept for diag."""
    for pipe in candidates(monitor):
        probe = [ffmpeg(), "-v", "error", "-y", *pipe.args, "-t", "2", "-f", "null", "-"]
        result = subprocess.run(probe, capture_output=True, text=True, errors="replace", timeout=30, **NO_WINDOW)
        if result.returncode == 0:
            return pipe
        PROBE_FAILURES[pipe.name] = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else f"exit {result.returncode}"
    raise RuntimeError("no working screen capture: " + "; ".join(f"{k}: {v}" for k, v in PROBE_FAILURES.items()))


class Recorder:
    """Keeps the last ~80 s of screen in `work_dir`; `save_replay` writes the last minute as one file."""

    def __init__(self, work_dir: Path, pipeline: Pipeline | None = None, segment_seconds: int = SEGMENT_SECONDS, monitor: int | None = None):
        self.work_dir = work_dir
        self.pipeline = pipeline
        self.monitor = monitor
        self.segment_seconds = segment_seconds
        self.process: subprocess.Popen | None = None

    def start(self) -> None:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        for old in self.work_dir.glob("seg*.ts"):
            old.unlink()
        self.pipeline = self.pipeline or pick_pipeline(self.monitor)
        cmd = [
            ffmpeg(), "-v", "error", "-y", *self.pipeline.args,
            "-f", "segment", "-segment_time", str(self.segment_seconds), "-segment_wrap", str(KEEP_SEGMENTS),
            "-reset_timestamps", "1", str(self.work_dir / "seg%02d.ts"),
        ]
        self.process = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stderr=(self.work_dir / "ffmpeg.log").open("ab"), **NO_WINDOW)

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
        subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", concat, "-c", "copy", "-movflags", "+faststart", str(out)], check=True, **NO_WINDOW)
        return str(out)
