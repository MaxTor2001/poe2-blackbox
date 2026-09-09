from datetime import timedelta
from pathlib import Path

from blackbox.journal import deaths
from blackbox.log_lines import parse_line

FIXTURE = Path(__file__).parent / "fixtures/client_sample.txt"


def test_death_gets_context():
    events = [e for e in map(parse_line, FIXTURE.read_text().splitlines()) if e]
    (d,) = deaths(events)
    assert (d.character, d.klass, d.char_level) == ("Zahrek", "Monk", 2)
    assert (d.zone, d.area_level) == ("Clearfell", 16)
    assert d.time_in_zone == timedelta(minutes=49, seconds=40)
