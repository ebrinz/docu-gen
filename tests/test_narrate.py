import json
import struct
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock
from docugen.tools.narrate import generate_narration, _apply_post_fx


PLAN = {
    "title": "Test",
    "chapters": [
        {
            "id": "intro",
            "title": "Introduction",
            "narration": "Welcome to this test documentary.",
            "scene_type": "manim",
            "images": [],
            "duration_estimate": 10.0,
        },
        {
            "id": "ch1",
            "title": "Chapter One",
            "narration": "This is the first chapter about testing.",
            "scene_type": "mixed",
            "images": ["shot1.png"],
            "duration_estimate": 20.0,
        },
    ],
}


def _make_fake_wav(sr=24000, seconds=2):
    n_samples = sr * seconds
    data_size = n_samples * 2  # 16-bit
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + data_size, b'WAVE',
        b'fmt ', 16, 1, 1, sr, sr * 2, 2, 16,
        b'data', data_size,
    )
    return header + b'\x00' * data_size


@pytest.fixture
def project_dir(tmp_path):
    (tmp_path / "config.yaml").write_text("title: Test\n")
    build = tmp_path / "build"
    build.mkdir()
    (build / "narration").mkdir()
    (build / "plan.json").write_text(json.dumps(PLAN))
    return tmp_path


def test_generate_narration_creates_wavs(project_dir):
    fake_wav = _make_fake_wav()

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = fake_wav
    mock_response.write_to_file = lambda path: Path(path).write_bytes(fake_wav)
    mock_client.audio.speech.create.return_value = mock_response

    with patch("docugen.tools.narrate.OpenAI", return_value=mock_client):
        result = generate_narration(project_dir)

    narration_dir = project_dir / "build" / "narration"
    assert (narration_dir / "intro.wav").exists()
    assert (narration_dir / "ch1.wav").exists()
    assert "intro.wav" in result
    assert "ch1.wav" in result


def test_generate_narration_chatterbox(tmp_path):
    """Chatterbox engine writes WAVs via _generate_chatterbox, post_fx only when configured."""
    import torch

    ref_wav = tmp_path / "ref.wav"
    ref_wav.write_bytes(_make_fake_wav())

    (tmp_path / "config.yaml").write_text(
        f"title: Test\n"
        f"voice:\n"
        f"  engine: chatterbox\n"
        f"  ref_audio: {ref_wav}\n"
        f"  exaggeration: 0.15\n"
        f"  cfg_weight: 0.8\n"
        f"  post_fx:\n"
        f"    ring_freq: 30\n"
        f"    formant_shift: 1.05\n"
        f"    dry_wet: 0.2\n"
    )
    build = tmp_path / "build"
    build.mkdir()
    (build / "narration").mkdir()
    (build / "plan.json").write_text(json.dumps(PLAN))

    fake_tensor = torch.zeros(1, 24000 * 2)  # 2s silence

    mock_model = MagicMock()
    mock_model.sr = 24000
    mock_model.generate.return_value = fake_tensor

    with patch("docugen.tools.narrate._get_chatterbox_model", return_value=mock_model):
        result = generate_narration(tmp_path)

    assert mock_model.generate.call_count == 2

    # Verify ref_audio and params passed correctly
    call_kwargs = mock_model.generate.call_args_list[0][1]
    assert call_kwargs["audio_prompt_path"] == str(ref_wav)
    assert call_kwargs["exaggeration"] == 0.15
    assert call_kwargs["cfg_weight"] == 0.8

    narration_dir = build / "narration"
    assert (narration_dir / "intro.wav").exists()
    assert (narration_dir / "ch1.wav").exists()
    assert "intro.wav" in result


def test_generate_narration_from_clips(tmp_path):
    """Clip-based: reads clips.json, generates one WAV per clip with per-clip exaggeration."""
    import torch

    ref_wav = tmp_path / "ref.wav"
    ref_wav.write_bytes(_make_fake_wav())

    (tmp_path / "config.yaml").write_text(
        f"title: Test\n"
        f"voice:\n"
        f"  engine: chatterbox\n"
        f"  ref_audio: {ref_wav}\n"
        f"  exaggeration: 0.15\n"
        f"  cfg_weight: 0.8\n"
    )
    build = tmp_path / "build"
    build.mkdir()
    (build / "narration").mkdir()

    clips_data = {
        "title": "Test",
        "theme": "biopunk",
        "chapters": [{
            "id": "ch1",
            "title": "One",
            "clips": [
                {"clip_id": "ch1_01", "text": "", "exaggeration": 0.3,
                 "emotion_tag": "neutral", "pacing": "normal",
                 "visuals": {"type": "chapter_card", "assets": [], "direction": ""}},
                {"clip_id": "ch1_02", "text": "Hello.", "exaggeration": 0.3,
                 "emotion_tag": "neutral", "pacing": "normal",
                 "visuals": {"type": "blank", "assets": [], "direction": ""}},
                {"clip_id": "ch1_03", "text": "World.", "exaggeration": 0.5,
                 "emotion_tag": "dramatic", "pacing": "breathe",
                 "visuals": {"type": "blank", "assets": [], "direction": ""}},
            ],
        }],
    }
    (build / "clips.json").write_text(json.dumps(clips_data))

    fake_tensor = torch.zeros(1, 24000 * 2)
    mock_model = MagicMock()
    mock_model.sr = 24000
    mock_model.generate.return_value = fake_tensor

    with patch("docugen.tools.narrate._get_chatterbox_model", return_value=mock_model):
        result = generate_narration(tmp_path)

    # 2 clips with text (ch1_01 has no text, skipped)
    assert mock_model.generate.call_count == 2
    calls = mock_model.generate.call_args_list
    assert calls[0][1]["exaggeration"] == 0.3
    assert calls[1][1]["exaggeration"] == 0.5

    assert (build / "narration" / "ch1_02.wav").exists()
    assert (build / "narration" / "ch1_03.wav").exists()
    assert "ch1_02.wav" in result
    assert "ch1_03.wav" in result


def test_post_fx_no_effect_when_dry():
    """Post FX with dry_wet=0 returns input unchanged."""
    signal = np.random.randn(24000).astype(np.float32)
    result = _apply_post_fx(signal, 24000, {"dry_wet": 0})
    np.testing.assert_array_equal(result, signal)


def test_post_fx_applies_ring_and_formant():
    """Post FX with nonzero dry_wet actually modifies the signal."""
    signal = np.sin(2 * np.pi * 440 * np.arange(24000) / 24000).astype(np.float32)
    result = _apply_post_fx(signal, 24000, {
        "ring_freq": 30, "formant_shift": 1.05, "dry_wet": 0.2,
    })
    assert not np.array_equal(result, signal)
    assert np.abs(result).max() <= 0.96  # normalized to 0.95
