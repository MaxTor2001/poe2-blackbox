from pathlib import Path

from blackbox.tail import follow


def test_follow_yields_only_new_complete_lines(tmp_path: Path):
    log = tmp_path / "Client.txt"
    log.write_text("old line\n")
    gen = follow(log, poll_seconds=0.01)
    with log.open("a") as f:
        f.write("new one\npartial")
    assert next(gen) == "new one"
    with log.open("a") as f:
        f.write(" done\n")
    assert next(gen) == "partial done"


def test_follow_restarts_after_truncation(tmp_path: Path):
    log = tmp_path / "Client.txt"
    log.write_text("a\nb\nc\n")
    gen = follow(log, poll_seconds=0.01)
    log.write_text("x\n")
    assert next(gen) == "x"
