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
SYSTEM_MESSAGE = re.compile(r"\] : ")  # chat-style client messages: deaths, level ups, AFK, identified items


def report(log_path: Path | None, grep: str | None = None, clips_dir: Path | None = None) -> str:
    lines = [f"platform: {platform.platform()}", f"ffmpeg: {ffmpeg()} ({'found' if shutil.which(ffmpeg()) or Path(ffmpeg()).exists() else 'missing'})"]
    lines += _encoder_lines()
    from blackbox.gamewindow import game_monitor_index

    lines.append(f"game window: {'display ' + str(game_monitor_index()) if game_monitor_index() is not None else 'not found (is the game running?)'}")
    if clips_dir:
        lines += _clips_lines(clips_dir)
    path = log_path or default_log_path()
    lines.append(f"log: {path if path else 'not found'}")
    if path and path.exists():
        lines += _log_summary(path, grep)
    return "\n".join(lines)


def _encoder_lines() -> list[str]:
    from blackbox.capture import PROBE_FAILURES, pick_pipeline

    try:
        chosen = pick_pipeline().name
    except (RuntimeError, OSError, subprocess.SubprocessError) as err:
        chosen = f"none ({err})"
    return [f"capture: {chosen}"] + [f"  {name} failed: {why}" for name, why in PROBE_FAILURES.items()]


def _clips_lines(clips_dir: Path) -> list[str]:
    if not clips_dir.exists():
        return ["clips: no recordings yet"]
    segments = sorted(clips_dir.glob("seg*.ts"))
    clips = sorted(clips_dir.glob("death-*.mp4"))
    out = [f"clips: {len(segments)} segments, {len(clips)} saved clips in {clips_dir}"]
    log = clips_dir / "ffmpeg.log"
    if log.exists() and log.stat().st_size:
        out += ["  ffmpeg.log tail:"] + [f"    {l}" for l in log.read_text(errors="replace").splitlines()[-5:]]
    return out


def _log_summary(path: Path, grep: str | None) -> list[str]:
    kinds: Counter = Counter()
    shapes: Counter = Counter()
    messages: Counter = Counter()
    grep_hits: list[str] = []
    total = 0
    for line in read_all(path):
        total += 1
        if grep and grep in line and len(grep_hits) < 10:
            grep_hits.append(repr(line))
        event = parse_line(line)
        if event:
            kinds[event.kind] += 1
            continue
        if "] " not in line:
            continue
        shape = DIGITS.sub("N", NOISE.sub("", line.rstrip()))[:110]
        shapes[shape] += 1
        if SYSTEM_MESSAGE.search(line):
            messages[shape] += 1
    out = [f"lines: {total}", "parsed: " + (", ".join(f"{k}={v}" for k, v in kinds.most_common()) or "nothing")]
    if grep:
        out += [f"raw lines containing {grep!r}:"] + [f"  {h}" for h in grep_hits]
    out.append("unparsed system messages (rare ones first, these are where deaths and level ups hide):")
    out += [f"  {n:5}  {shape}" for shape, n in sorted(messages.items(), key=lambda kv: kv[1])[:60]]
    out.append("unparsed shapes (most common):")
    out += [f"  {n:5}  {shape}" for shape, n in shapes.most_common(25)]
    return out
