"""Diagnostics: what this machine has, and what in the log we do not understand yet."""

import platform
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

from blackbox.log_lines import parse_line
from blackbox.paths import default_log_path, ffmpeg
from blackbox.tail import read_all

NOISE = re.compile(r"^\S+ \S+ \d+ [0-9a-f]+ ")  # timestamp + counters at the start of every line
DIGITS = re.compile(r"\d+")


def report(log_path: Path | None) -> str:
    lines = [f"platform: {platform.platform()}", f"ffmpeg: {ffmpeg()} ({'found' if shutil.which(ffmpeg()) or Path(ffmpeg()).exists() else 'missing'})"]
    try:
        from blackbox.capture import pick_encoder

        lines.append(f"encoder: {pick_encoder()[1]}")
    except (RuntimeError, OSError, subprocess.SubprocessError) as err:
        lines.append(f"encoder: none ({err})")
    path = log_path or default_log_path()
    lines.append(f"log: {path if path else 'not found'}")
    if path and path.exists():
        lines += _log_summary(path)
    return "\n".join(lines)


def _log_summary(path: Path) -> list[str]:
    kinds: Counter = Counter()
    shapes: Counter = Counter()
    total = 0
    for line in read_all(path):
        total += 1
        event = parse_line(line)
        if event:
            kinds[event.kind] += 1
        elif "] " in line:
            shapes[DIGITS.sub("N", NOISE.sub("", line.rstrip()))[:110]] += 1
    out = [f"lines: {total}", "parsed: " + ", ".join(f"{k}={v}" for k, v in kinds.most_common()) or "parsed: nothing"]
    out.append("unparsed shapes (most common):")
    out += [f"  {n:5}  {shape}" for shape, n in shapes.most_common(40)]
    return out
