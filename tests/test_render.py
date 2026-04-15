import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from docugen.tools.render import build_manim_script, render_all


def test_build_manim_script_intro():
    chapter = {
        "id": "intro",
        "title": "Introduction",
        "narration": "Welcome to this documentary.",
        "scene_type": "manim",
        "images": [],
        "duration_estimate": 10.0,
    }
    script = build_manim_script(
        chapter=chapter,
        doc_title="Test Documentary",
        duration=10.0,
        images_dir=Path("/fake/images"),
    )
    assert "class Scene_intro" in script
    assert "Test Documentary" in script


def test_build_manim_script_mixed_with_images():
    chapter = {
        "id": "ch1",
        "title": "Chapter One",
        "narration": "This chapter has images.",
        "scene_type": "mixed",
        "images": ["shot1.png", "diagram.jpg"],
        "duration_estimate": 30.0,
    }
    script = build_manim_script(
        chapter=chapter,
        doc_title="Test Documentary",
        duration=30.0,
        images_dir=Path("/fake/images"),
    )
    assert "class Scene_ch1" in script
    assert "shot1.png" in script


def test_build_manim_script_outro():
    chapter = {
        "id": "outro",
        "title": "Conclusion",
        "narration": "Thank you for watching.",
        "scene_type": "manim",
        "images": [],
        "duration_estimate": 12.0,
    }
    script = build_manim_script(
        chapter=chapter,
        doc_title="Test Documentary",
        duration=12.0,
        images_dir=Path("/fake/images"),
    )
    assert "class Scene_outro" in script


def test_render_all_calls_compose(tmp_path):
    clips_data = {
        "title": "Test",
        "theme": "biopunk",
        "chapters": [{
            "id": "intro",
            "title": "Intro",
            "clips": [{
                "clip_id": "intro_01",
                "text": "Hello",
                "visuals": {"slide_type": "data_text", "cue_words": [], "assets": []},
                "timing": {"clip_duration": 5.0},
            }],
        }],
    }
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "clips.json").write_text(json.dumps(clips_data))
    (tmp_path / "images").mkdir()
    (tmp_path / "config.yaml").write_text("title: Test\n")

    (tmp_path / "build" / "clips").mkdir(parents=True, exist_ok=True)
    with patch("docugen.compose.render_clip_dag") as mock_dag:
        out_path = tmp_path / "build" / "clips" / "intro_01.mp4"
        mock_dag.return_value = out_path
        # Don't create the mp4 beforehand — let render_all call the DAG
        result = render_all(str(tmp_path))
        assert mock_dag.called
        assert "intro_01" in result
