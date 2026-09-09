from pathlib import Path

from blackbox.log_lines import parse_line
from blackbox.store import Store

FIXTURE = Path(__file__).parent / "fixtures/client_sample.txt"


def test_import_is_idempotent(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    events = [e for e in map(parse_line, FIXTURE.read_text().splitlines()) if e]
    assert sum(store.add(e) for e in events) == 6
    assert sum(store.add(e) for e in events) == 0
    assert [e.kind for e in store.events("death")] == ["death"]
