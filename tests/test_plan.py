import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from docugen.tools.plan import extract_pdf_text, generate_plan, list_images


@pytest.fixture
def project_dir(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "title: Test Doc\n"
    )
    (tmp_path / "prompt.txt").write_text("Make it engaging.\n")
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "shot1.png").write_bytes(b"fake png")
    (tmp_path / "images" / "diagram.jpg").write_bytes(b"fake jpg")
    (tmp_path / "build").mkdir()
    return tmp_path


def test_list_images(project_dir):
    images = list_images(project_dir)
    assert sorted(images) == ["diagram.jpg", "shot1.png"]


def test_extract_pdf_text_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        extract_pdf_text(tmp_path / "nonexistent.pdf")


def test_generate_plan_writes_json(project_dir):
    fake_chapters = {
        "title": "Test Doc",
        "chapters": [
            {
                "id": "intro",
                "title": "Introduction",
                "narration": "Welcome to this documentary.",
                "scene_type": "manim",
                "images": [],
                "duration_estimate": 10.0,
            }
        ],
    }

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps(fake_chapters)
    mock_client.chat.completions.create.return_value = mock_response

    with patch("docugen.tools.plan.OpenAI", return_value=mock_client):
        result = generate_plan(project_dir, pdf_text="Some spec content.")

    plan_path = project_dir / "build" / "plan.json"
    assert plan_path.exists()

    plan = json.loads(plan_path.read_text())
    assert plan["title"] == "Test Doc"
    assert len(plan["chapters"]) == 1
    assert plan["chapters"][0]["id"] == "intro"
    assert result == str(plan_path)
