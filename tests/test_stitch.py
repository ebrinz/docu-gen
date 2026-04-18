import json
import numpy as np
import pytest
from pathlib import Path
from scipy.io import wavfile
from unittest.mock import patch
from docugen.tools.stitch import (
    load_narration_tracks,
    mix_audio,
)


def _write_test_wav(path: Path, duration: float, sr: int = 44100, stereo: bool = False):
    """Write a silent WAV file for testing."""
    n_samples = int(duration * sr)
    if stereo:
        data = np.zeros((n_samples, 2), dtype=np.int16)
    else:
        data = np.zeros(n_samples, dtype=np.int16)
    wavfile.write(str(path), sr, data)


@pytest.fixture
def project_dir(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "title: Test\n"
        "drone:\n"
        "  cutoff_hz: 400\n"
        "  duck_db: -18\n"
        "  rt60: 1.5\n"
        "  cue_freq: 220\n"
    )
    build = tmp_path / "build"
    build.mkdir()
    narration = build / "narration"
    narration.mkdir()
    clips = build / "clips"
    clips.mkdir()

    plan = {
        "title": "Test",
        "chapters": [
            {"id": "intro", "title": "Intro", "narration": "...",
             "scene_type": "manim", "images": [], "duration_estimate": 5.0},
            {"id": "ch1", "title": "Ch1", "narration": "...",
             "scene_type": "mixed", "images": [], "duration_estimate": 10.0},
        ],
    }
    (build / "plan.json").write_text(json.dumps(plan))

    _write_test_wav(narration / "intro.wav", 5.0)
    _write_test_wav(narration / "ch1.wav", 10.0)

    return tmp_path


def test_load_narration_tracks(project_dir):
    tracks = load_narration_tracks(project_dir)
    assert "intro" in tracks
    assert "ch1" in tracks
    assert tracks["intro"]["duration"] == pytest.approx(5.0, abs=0.1)


def test_mix_audio_output_shape():
    sr = 44100
    n = sr * 10
    voice = np.zeros((n, 2))
    drone = np.random.default_rng(0).standard_normal((n, 2)) * 0.1
    mixed = mix_audio(voice, drone, duck_db=-18, sr=sr)
    assert mixed.shape == (n, 2)
    assert np.max(np.abs(mixed)) <= 1.0 + 1e-6


def test_stitch_auto_generates_title_when_missing(tmp_path, monkeypatch):
    """If build/title.mp4 is absent, stitch must invoke generate_title."""
    from docugen.tools import stitch as stitch_mod

    build = tmp_path / "build"
    build.mkdir()
    (build / "clips.json").write_text('{"chapters":[]}')
    (tmp_path / "config.yaml").write_text("title: T\n")

    called = {"n": 0}
    def fake_title(project_path, **kwargs):
        called["n"] += 1
        (tmp_path / "build" / "title.mp4").write_bytes(b"fake")
        return "ok"

    monkeypatch.setattr(stitch_mod, "generate_title", fake_title)
    # Prevent the rest of stitch from running — we only care about the title branch
    monkeypatch.setattr(stitch_mod, "_stitch_from_clips", lambda p: "stub")

    stitch_mod.stitch_all(tmp_path)
    assert called["n"] == 1


def test_stitch_skips_title_when_present(tmp_path, monkeypatch):
    from docugen.tools import stitch as stitch_mod

    build = tmp_path / "build"
    build.mkdir()
    (build / "clips.json").write_text('{"chapters":[]}')
    (build / "title.mp4").write_bytes(b"existing")
    (tmp_path / "config.yaml").write_text("title: T\n")

    called = {"n": 0}
    def fake_title(project_path, **kwargs):
        called["n"] += 1
        return "ok"

    monkeypatch.setattr(stitch_mod, "generate_title", fake_title)
    monkeypatch.setattr(stitch_mod, "_stitch_from_clips", lambda p: "stub")

    stitch_mod.stitch_all(tmp_path)
    assert called["n"] == 0


def test_stitch_skips_title_when_skip_marker_present(tmp_path, monkeypatch):
    """Users can opt out by touching build/title.mp4.skip."""
    from docugen.tools import stitch as stitch_mod

    build = tmp_path / "build"
    build.mkdir()
    (build / "clips.json").write_text('{"chapters":[]}')
    (build / "title.mp4.skip").write_text("")
    (tmp_path / "config.yaml").write_text("title: T\n")

    called = {"n": 0}
    def fake_title(project_path, **kwargs):
        called["n"] += 1
        return "ok"

    monkeypatch.setattr(stitch_mod, "generate_title", fake_title)
    monkeypatch.setattr(stitch_mod, "_stitch_from_clips", lambda p: "stub")

    stitch_mod.stitch_all(tmp_path)
    assert called["n"] == 0
