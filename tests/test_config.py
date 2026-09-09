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


def test_config_file_is_owner_only(tmp_path, monkeypatch):
    import os
    import sys

    monkeypatch.setattr(config, "data_dir", lambda: tmp_path)
    config.save(sessid="secret")
    if sys.platform != "win32":
        assert os.stat(config.config_path()).st_mode & 0o777 == 0o600
