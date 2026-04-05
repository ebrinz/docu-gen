import pytest
from pathlib import Path
from docugen.config import load_config


def test_load_config_reads_yaml(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "title: Test Doc\n"
        "voice:\n"
        "  model: tts-1-hd\n"
        "  voice: echo\n"
        "video:\n"
        "  resolution: 1080p\n"
        "  fps: 60\n"
        "drone:\n"
        "  cutoff_hz: 400\n"
        "  duck_db: -18\n"
        "  rt60: 1.5\n"
        "  cue_freq: 220\n"
    )
    cfg = load_config(tmp_path)
    assert cfg["title"] == "Test Doc"
    assert cfg["voice"]["model"] == "tts-1-hd"
    assert cfg["voice"]["voice"] == "echo"
    assert cfg["video"]["fps"] == 60
    assert cfg["drone"]["cutoff_hz"] == 400


def test_load_config_defaults(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("title: Minimal\n")
    cfg = load_config(tmp_path)
    assert cfg["voice"]["model"] == "tts-1-hd"
    assert cfg["voice"]["voice"] == "echo"
    assert cfg["video"]["resolution"] == "1080p"
    assert cfg["video"]["fps"] == 60
    assert cfg["drone"]["cutoff_hz"] == 400
    assert cfg["drone"]["duck_db"] == -18
    assert cfg["drone"]["rt60"] == 1.5
    assert cfg["drone"]["cue_freq"] == 220


def test_load_config_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path)
