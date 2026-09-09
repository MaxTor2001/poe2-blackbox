from blackbox import config
from blackbox.character import name_forms


def test_config_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "data_dir", lambda: tmp_path)
    assert config.load() == {}
    assert config.save(account="Max#1", sessid=None) == {"account": "Max#1"}
    assert config.save(sessid="abc") == {"account": "Max#1", "sessid": "abc"}


def test_name_forms():
    assert name_forms("Max#7804") == ["Max#7804", "Max-7804"]
    assert name_forms("Max-7804") == ["Max-7804", "Max#7804"]
    assert name_forms("Max") == ["Max"]
