from pathlib import Path

from blackbox.diag import report

FIXTURE = Path(__file__).parent / "fixtures/client_sample.txt"


def test_report_counts_and_unparsed_shapes():
    text = report(FIXTURE)
    assert "death=2" in text and "zone=2" in text
    assert "N Items identified" in text
    unparsed = text.split("unparsed shapes")[1]
    assert "@From Trader" in unparsed
    assert ": Zahrek has been slain." not in unparsed


def test_grep_shows_raw_lines():
    text = report(FIXTURE, grep="instance server")
    assert "raw lines containing" in text and "101.100.146.42" in text
