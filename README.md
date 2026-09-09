# poe2-blackbox

[Русская версия](README.ru.md)

Hardcore black box for Path of Exile 2. Runs on the player's machine, reads `Client.txt`, and records
every death with context: zone, area level, character level, time in zone, waystone mods, ping to the
instance server, gear snapshot, and a video clip of the last minute.

```
uv run blackbox watch  --log /path/to/Client.txt   # follow the log, record everything
uv run blackbox serve                              # death journal at http://127.0.0.1:8765/
uv run blackbox import --log /path/to/Client.txt   # parse an existing log once
uv run blackbox deaths                             # deaths in the terminal
uv run pytest
```

`--log` is optional when the game is installed in the default Steam location on Linux.

## What is collected and how

- **Log events**: zone changes, area generation (level, seed), level ups, deaths, instance server
  connections. All from `Client.txt`, nothing else is read from the game.
- **Ping**: a TCP connect to the current instance server every 2 s; the journal shows avg, max and
  lost samples for the minute before each death.
- **Waystone mods**: Ctrl+C a waystone before running it; the copied text is parsed from the
  clipboard and attached to deaths in that map.
- **Gear snapshot**: on zone entry, at most once a minute, from the pathofexile.com character window.
  The site only answers logged-in sessions, so run once with `--account "Name#1234" --sessid <POESESSID>`
  (the cookie from your browser on pathofexile.com); both are remembered in `config.json` in the data
  folder, in plain text, on your machine only. Stored snapshots are raw JSON. NOTE: PoE2 gear needs GGG's official OAuth API (realm poe2), whose app registration is currently closed, so this is wired up but inactive until it opens; the rest of the journal works without it.
- **Death clips**: `watch` records the screen with ffmpeg into a ring of short segments next to the
  database (`clips/`), and a few seconds after every death saves the last minute as an mp4 linked
  from the journal. Needs `ffmpeg` on PATH; uses NVENC when available, otherwise libx264 at 1080p.
  `--no-clips` disables recording. Streamers who already run OBS with a replay buffer can pass
  `--obs` to use it instead (enable obs-websocket; `--obs-password` / `OBS_PASSWORD` if it has one).

Database, clips and `blackbox.log` live in the per-user data folder (`%LOCALAPPDATA%\\poe2-blackbox` on Windows,
`~/.local/share/poe2-blackbox` on Linux), so updating the program keeps your history. On first start the
existing log is imported, so past deaths appear right away.

Everything stays on your machine. Nothing is uploaded.

This product isn't affiliated with or endorsed by Grinding Gear Games in any way.
