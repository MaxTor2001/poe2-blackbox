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
    from blackbox.gamewindow import game_monitor_index, visible_windows

    idx = game_monitor_index()
    lines.append(f"game window: {'display ' + str(idx) if idx is not None else 'not found (is the game running?)'}")
    from blackbox.gamewindow import game_windows, process_name

    exile = [f"{t} [{process_name(h) or '?'}]" for h, t in visible_windows() if "exile" in t.lower()]
    if exile:
        lines.append("windows mentioning exile: " + "; ".join(exile))
    lines.append(f"game windows matched: {len(game_windows())}")
    if clips_dir:
        lines += _clips_lines(clips_dir)
    from blackbox import config

    saved = config.load()
    lines.append(f"settings: {config.config_path()} ({'exists' if config.config_path().exists() else 'missing'}) account={saved.get('account') or 'none'} sessid={'set' if saved.get('sessid') else 'none'}")
    if saved.get("sessid"):
        lines += _account_probe(saved.get("account"), saved.get("sessid"))
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
    lines = [f"capture: {chosen}"] + [f"  {name} failed: {why}" for name, why in PROBE_FAILURES.items()]
    if PROBE_FAILURES:
        lines.append("nvenc alone: " + _nvenc_alone())
    return lines


def _nvenc_alone() -> str:
    """Encode a synthetic clip with NVENC, no screen capture involved, and report the first error lines."""
    cmd = [ffmpeg(), "-v", "error", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30", "-t", "1", "-c:v", "h264_nvenc", "-f", "null", "-"]
    result = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=30)
    if result.returncode == 0:
        return "works"
    return " | ".join(result.stderr.strip().splitlines()[:4]) or f"exit {result.returncode}"


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


def _account_probe(account: str | None, sessid: str) -> list[str]:
    """List characters each host/realm returns, so we can see which one has the PoE2 characters."""
    from blackbox.character import HOSTS, _characters, name_forms

    out = ["account probe:"]
    queries = [{}] + [{"accountName": f} for f in name_forms(account or "")]
    for base, realm in HOSTS:
        host = base.split("/")[2] + ("?" + "&".join(f"{k}={v}" for k, v in realm.items()) if realm else "")
        for q in queries:
            label = q.get("accountName", "(session)")
            try:
                names = [c.get("name", "?") for c in _characters(q, sessid, base, realm)]
                out.append(f"  {host} [{label}]: {names[:12] or 'none'}")
            except Exception as err:
                out.append(f"  {host} [{label}]: error {err!r}")
    return out
