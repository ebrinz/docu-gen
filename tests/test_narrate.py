import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from docugen.tools.narrate import generate_narration


@pytest.fixture
def project_dir(tmp_path):
    (tmp_path / "config.yaml").write_text("title: Test\n")
    build = tmp_path / "build"
    build.mkdir()
    (build / "narration").mkdir()

    plan = {
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
    (build / "plan.json").write_text(json.dumps(plan))
    return tmp_path


def test_generate_narration_creates_wavs(project_dir):
    import struct
    sr = 24000
    n_samples = sr * 2  # 2 seconds
    data_size = n_samples * 2  # 16-bit
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + data_size, b'WAVE',
        b'fmt ', 16, 1, 1, sr, sr * 2, 2, 16,
        b'data', data_size,
    )
    fake_wav = header + b'\x00' * data_size

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
