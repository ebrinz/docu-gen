import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from docugen.tools.render import build_manim_script, render_chapter, build_clip_script


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


def test_build_clip_script_blank(tmp_path):
    clip = {
        "clip_id": "ch1_01",
        "text": "Hello.",
        "visuals": {"type": "blank", "assets": [], "direction": ""},
    }
    script = build_clip_script(clip, theme_name="biopunk",
                               duration=5.0, images_dir=str(tmp_path))
    assert "class Scene_ch1_01" in script
    assert "def construct" in script


def test_build_clip_script_chapter_card(tmp_path):
    clip = {
        "clip_id": "ch2_01",
        "text": "",
        "visuals": {"type": "chapter_card", "assets": [], "direction": ""},
    }
    script = build_clip_script(clip, theme_name="biopunk",
                               duration=4.0, images_dir=str(tmp_path),
                               chapter_num="02", chapter_title="THE METHOD")
    assert "class Scene_ch2_01" in script
    assert "THE METHOD" in script


def test_build_clip_script_image_reveal(tmp_path):
    clip = {
        "clip_id": "ch3_02",
        "text": "Look at this.",
        "visuals": {"type": "image_reveal", "assets": ["fig.svg"],
                    "direction": "Fade in, zoom 1.04x"},
    }
    script = build_clip_script(clip, theme_name="biopunk",
                               duration=8.0, images_dir=str(tmp_path))
    assert "class Scene_ch3_02" in script
    assert "fig.svg" in script
