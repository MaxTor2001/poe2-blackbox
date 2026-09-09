from datetime import datetime
from pathlib import Path

from blackbox.log_lines import parse_line

FIXTURE = Path(__file__).parent / "fixtures/client_sample.txt"


def parsed():
    return [e for e in map(parse_line, FIXTURE.read_text().splitlines()) if e]


def test_only_known_lines_produce_events():
    assert [e.kind for e in parsed()] == ["area", "zone", "area", "zone", "level_up", "death"]


def test_death():
    death = parsed()[-1]
    assert death.ts == datetime(2025, 1, 16, 21, 56, 41)
    assert death.data == {"character": "Zahrek"}


def test_level_up():
    assert parsed()[4].data == {"character": "Zahrek", "class": "Monk", "level": 2}


def test_area_generation():
    assert parsed()[0].data == {"level": 15, "area_id": "G1_town", "seed": 1}


def test_zone_both_formats():
    zones = [e.data["name"] for e in parsed() if e.kind == "zone"]
    assert zones == ["Clearfell Encampment", "Clearfell"]


def test_whisper_containing_slain_is_ignored():
    line = "2025/01/16 21:57:00 1 a [INFO Client 1] : @From Trader: hi, has been slain. is a weird item name"
    assert parse_line(line) is None
