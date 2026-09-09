from blackbox.paths import default_log_path, ffmpeg


def test_ffmpeg_falls_back_to_path():
    assert ffmpeg().endswith("ffmpeg")


def test_default_log_path_is_none_without_game():
    assert default_log_path() is None
