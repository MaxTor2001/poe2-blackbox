# blackbox

Hardcore black box for Path of Exile 2. Reads `Client.txt`, records deaths with context.

Done: zone changes, area generation, level ups and deaths go to SQLite; a local web page shows the death journal.

```
uv run blackbox import --log /path/to/Client.txt   # parse the whole log once
uv run blackbox watch  --log /path/to/Client.txt   # follow the log live
uv run blackbox deaths                             # deaths with zone and area level
uv run blackbox serve                              # death journal at http://127.0.0.1:8765/
uv run pytest
```

`--log` is optional when the game is installed in the default Steam location on Linux.

Roadmap: ping to instance server, character snapshot via OAuth API, waystone mods
from clipboard, death clip via OBS replay buffer.
