"""Built-in screen recorder: ffmpeg writes a ring of short segments, a clip is the last minute."""

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from blackbox.paths import ffmpeg

SEGMENT_SECONDS = 5
KEEP_SEGMENTS = 14  # 70 s of history, enough for the longest --clip-seconds we allow
CLIP_SECONDS = 30
PROBE_FAILURES: dict[str, str] = {}
NO_WINDOW = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}  # ffmpeg must not pop a console


@dataclass
class Pipeline:
    """A complete capture+encode setup, cheapest variants first in `candidates()`."""

    name: str
    args: list[str]


NVENC = ["-c:v", "h264_nvenc", "-preset", "p1", "-tune", "ll", "-delay", "0", "-bf", "0", "-rc-lookahead", "0", "-b:v", "8M", "-g", "30"]
X264 = ["-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-g", "30"]
QSV = ["-pix_fmt", "nv12", "-c:v", "h264_qsv", "-preset", "veryfast", "-b:v", "8M", "-g", "30"]
AMF = ["-pix_fmt", "yuv420p", "-c:v", "h264_amf", "-usage", "lowlatency", "-b:v", "8M", "-g", "30"]


def crop_filter(rect: tuple[int, int, int, int] | None) -> str:
    """ffmpeg crop for the game window; empty when unknown. Even sizes keep yuv420p encoders happy."""
    if not rect:
        return ""
    x, y, w, h = rect
    return f"crop={w // 2 * 2}:{h // 2 * 2}:{x}:{y},"


def candidates(monitor: int | None = None, rect: tuple[int, int, int, int] | None = None) -> list[Pipeline]:
    if sys.platform == "win32":
        dda = f"ddagrab=output_idx={monitor or 0}"
        crop = crop_filter(rect)
        return [
            Pipeline("ddagrab+nvenc (GPU only)", ["-init_hw_device", "d3d11va", "-filter_complex", f"{dda}:framerate=30", *NVENC]),
            Pipeline("ddagrab+nvenc 1080p", ["-init_hw_device", "d3d11va", "-filter_complex", f"{dda}:framerate=30,hwdownload,format=bgra,{crop}scale=-2:'min(1080,ih)'", "-pix_fmt", "yuv420p", *NVENC]),
            Pipeline("ddagrab+qsv 1080p", ["-init_hw_device", "d3d11va", "-filter_complex", f"{dda}:framerate=30,hwdownload,format=bgra,{crop}scale=-2:'min(1080,ih)'", *QSV]),
            Pipeline("ddagrab+amf 1080p", ["-init_hw_device", "d3d11va", "-filter_complex", f"{dda}:framerate=30,hwdownload,format=bgra,{crop}scale=-2:'min(1080,ih)'", *AMF]),
            Pipeline("ddagrab+x264 720p", ["-init_hw_device", "d3d11va", "-filter_complex", f"{dda}:framerate=24,hwdownload,format=bgra,{crop}scale=-2:720", *X264]),
            Pipeline("gdigrab+x264 720p", ["-f", "gdigrab", "-framerate", "20", "-i", "desktop", "-vf", f"{crop}scale=-2:720", *X264]),
        ]
    display = os.environ.get("DISPLAY", ":0")
    grab = ["-f", "x11grab", "-framerate", "30", "-i", display]
    return [
        Pipeline("x11grab+nvenc", [*grab, "-vf", "scale=-2:'min(1080,ih)'", "-pix_fmt", "yuv420p", *NVENC]),
        Pipeline("x11grab+x264 1080p", [*grab, "-vf", "scale=-2:'min(1080,ih)'", *X264]),
    ]


def pick_pipeline(monitor: int | None = None, rect=None) -> Pipeline:
    """First pipeline that records two seconds on this machine; failures are kept for diag."""
    for pipe in candidates(monitor, rect):
        probe = [ffmpeg(), "-v", "error", "-y", *pipe.args, "-t", "2", "-f", "null", "-"]
        result = subprocess.run(probe, capture_output=True, text=True, errors="replace", timeout=30, **NO_WINDOW)
        if result.returncode == 0:
            return pipe
        PROBE_FAILURES[pipe.name] = " | ".join(result.stderr.strip().splitlines()[-4:]) or f"exit {result.returncode}"
    raise RuntimeError("no working screen capture: " + "; ".join(f"{k}: {v}" for k, v in PROBE_FAILURES.items()))


class Recorder:
    """Keeps the last ~70 s of screen in `work_dir`; `save_replay` writes the last `clip_seconds` as one file."""

    def __init__(self, work_dir: Path, pipeline: Pipeline | None = None, segment_seconds: int = SEGMENT_SECONDS, monitor: int | None = None, clip_seconds: int = CLIP_SECONDS):
        self.work_dir = work_dir
        self.pipeline = pipeline
        self.monitor = monitor
        self.segment_seconds = segment_seconds
        self.clip_seconds = clip_seconds
        self.process: subprocess.Popen | None = None

    @staticmethod
    def window_rect():
        from blackbox.gamewindow import game_window_rect

        return game_window_rect()

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self) -> None:
        if self.running:
            return
        self.work_dir.mkdir(parents=True, exist_ok=True)
        for old in self.work_dir.glob("seg*.ts"):
            old.unlink()
        rect = self.window_rect()
        if self.pipeline is None:
            self.pipeline = pick_pipeline(self.monitor, rect)
        else:  # keep the proven pipeline, refresh the crop for the current window position
            self.pipeline = next((c for c in candidates(self.monitor, rect) if c.name == self.pipeline.name), self.pipeline)
        cmd = [
            ffmpeg(), "-v", "error", "-y", *self.pipeline.args,
            "-f", "segment", "-segment_time", str(self.segment_seconds), "-segment_wrap", str(KEEP_SEGMENTS),
            "-reset_timestamps", "1", str(self.work_dir / "seg%02d.ts"),
        ]
        self.process = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stderr=(self.work_dir / "ffmpeg.log").open("ab"), **NO_WINDOW)

    def stop(self) -> None:
        if self.running:
            self.process.terminate()
            self.process.wait(timeout=10)
        self.process = None

    def save_replay(self) -> str:
        """Concatenate the segments touched within the last `clip_seconds` into one mp4."""
        cutoff = time.time() - self.clip_seconds - self.segment_seconds
        recent = sorted((p for p in self.work_dir.glob("seg*.ts") if p.stat().st_mtime >= cutoff), key=lambda p: p.stat().st_mtime)
        if not recent:
            raise RuntimeError("no recorded segments yet")
        out = self.work_dir / f"death-{datetime.now():%Y-%m-%d_%H-%M-%S}.mp4"
        concat = "concat:" + "|".join(str(p) for p in recent)
        subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", concat, "-c", "copy", "-movflags", "+faststart", str(out)], check=True, **NO_WINDOW)
        return str(out)
