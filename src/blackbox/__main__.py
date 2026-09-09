"""Entry point for `python -m blackbox` and the frozen executable: no arguments means `run`."""

import sys
from pathlib import Path

from blackbox.cli import cli

if __name__ == "__main__":
    if sys.stdout is None or sys.stderr is None:  # windowed build: no console at all
        import os

        from blackbox import cli as cli_module

        cli_module.HEADLESS = True
        sys.stdout = sys.stdout or open(os.devnull, "w")
        sys.stderr = sys.stderr or open(os.devnull, "w")
    if len(sys.argv) == 1:
        sys.argv.append("run")
    try:
        cli()
    except SystemExit:
        raise
    except Exception:
        # a windowed build has nowhere to print; leave a trace next to the executable
        import traceback

        Path("blackbox-crash.log").write_text(traceback.format_exc())
        raise
