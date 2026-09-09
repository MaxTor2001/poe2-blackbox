from pathlib import Path

from blackbox.cli import backfill
from blackbox.store import Store

FIXTURE = Path(__file__).parent / "fixtures/client_sample.txt"


def test_backfill_only_into_empty_db(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    assert backfill(store, FIXTURE) == 9
    assert backfill(store, FIXTURE) == 0
