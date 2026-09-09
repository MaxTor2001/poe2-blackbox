from pathlib import Path

from fastapi.testclient import TestClient

from blackbox.log_lines import parse_line
from blackbox.store import Store
from blackbox.web import create_app

FIXTURE = Path(__file__).parent / "fixtures/client_sample.txt"


def test_index_lists_deaths(tmp_path):
    db = tmp_path / "t.sqlite"
    store = Store(db)
    for e in filter(None, map(parse_line, FIXTURE.read_text().splitlines())):
        store.add(e)
    html = TestClient(create_app(db)).get("/").text
    assert "Zahrek" in html and "Clearfell" in html


def test_index_empty(tmp_path):
    html = TestClient(create_app(tmp_path / "empty.sqlite")).get("/").text
    assert "No deaths recorded yet" in html
