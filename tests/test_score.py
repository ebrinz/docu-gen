import json
import struct
import pytest
from pathlib import Path
from docugen.tools.score import generate_score


def _make_fake_wav(sr=24000, seconds=2):
    n = sr * seconds
    data_size = n * 2
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + data_size, b'WAVE',
        b'fmt ', 16, 1, 1, sr, sr * 2, 2, 16,
        b'data', data_size,
    )
    return header + b'\x00' * data_size


def test_generate_score_from_clips(tmp_path):
    (tmp_path / "config.yaml").write_text("title: Test\ntheme: biopunk\n")
    build = tmp_path / "build"
    build.mkdir()
    narr = build / "narration"
    narr.mkdir()

    clips_data = {
        "title": "Test",
        "theme": "biopunk",
        "chapters": [{
            "id": "ch1",
            "title": "One",
            "clips": [
                {"clip_id": "ch1_01", "text": "Hello.", "exaggeration": 0.3,
                 "emotion_tag": "neutral", "pacing": "normal",
                 "visuals": {"type": "blank", "assets": [], "direction": ""}},
            ],
        }],
    }
    (build / "clips.json").write_text(json.dumps(clips_data))
    (narr / "ch1_01.wav").write_bytes(_make_fake_wav())

    result = generate_score(tmp_path)
    score_path = build / "score.wav"
    assert score_path.exists()
    assert score_path.stat().st_size > 0
    assert "score.wav" in result


def test_generate_score_from_plan(tmp_path):
    """Falls back to plan.json when no clips.json."""
    (tmp_path / "config.yaml").write_text("title: Test\ntheme: biopunk\n")
    build = tmp_path / "build"
    build.mkdir()
    narr = build / "narration"
    narr.mkdir()

    plan = {
        "title": "Test",
        "chapters": [{"id": "intro", "title": "Intro",
                       "narration": "Hello.", "duration_s": 5}],
    }
    (build / "plan.json").write_text(json.dumps(plan))
    (narr / "intro.wav").write_bytes(_make_fake_wav())

    result = generate_score(tmp_path)
    assert (build / "score.wav").exists()
