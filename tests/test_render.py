import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from docugen.tools.render import build_manim_script, render_chapter


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
    assert "Introduction" in script


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
    assert "Chapter One" in script


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
    assert "Conclusion" in script
