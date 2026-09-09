from datetime import timedelta
from pathlib import Path

from blackbox.journal import deaths
from blackbox.log_lines import parse_line

FIXTURE = Path(__file__).parent / "fixtures/client_sample.txt"


def test_death_gets_context():
    events = [e for e in map(parse_line, FIXTURE.read_text().splitlines()) if e]
    d = deaths(events)[0]
    assert (d.character, d.klass, d.char_level) == ("Zahrek", "Monk", 2)
    assert (d.zone, d.area_level) == ("Clearfell", 16)
    assert d.time_in_zone == timedelta(minutes=49, seconds=41)


def test_summary_counts():
    from blackbox.journal import summary

    events = [e for e in map(parse_line, FIXTURE.read_text().splitlines()) if e]
    s = summary(deaths(events))
    assert s["total"] == 2
    assert [name for name, _ in s["characters"]] == ["Kelthuzard_Lich", "Zahrek"]
