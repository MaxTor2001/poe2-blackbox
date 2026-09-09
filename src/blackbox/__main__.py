"""Entry point for `python -m blackbox` and the frozen executable: no arguments means `run`."""

import sys

from blackbox.cli import cli

if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.append("run")
    cli()
