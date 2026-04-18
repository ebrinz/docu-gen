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

    (tmp_path / "build" / "frames").mkdir(parents=True, exist_ok=True)
    with patch("docugen.compose.render_clip_dag") as mock_dag:
        out_path = tmp_path / "build" / "frames" / "intro_01.mp4"
        mock_dag.return_value = out_path
        # Don't create the mp4 beforehand — let render_all call the DAG
        result = render_all(str(tmp_path))
        assert mock_dag.called
        assert "intro_01" in result


def test_render_chapter_output_path_is_frames_not_clips(tmp_path, monkeypatch):
    """render_chapter must write per-chapter outputs to build/frames/, not build/clips/."""
    import subprocess as _real_sp
    from docugen.tools import render as render_mod

    def fake_run(cmd, *args, **kwargs):
        class Result:
            returncode = 0
            stdout = b""
            stderr = b""
        # Simulate manim output: capture any rename targets and media-dir files
        for i, token in enumerate(cmd):
            if token == "--media_dir":
                media_dir = Path(cmd[i + 1])
                target = media_dir / "videos" / "_scene_intro" / "1080p60" / "Scene_intro.mp4"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"stub")
        return Result()

    monkeypatch.setattr("subprocess.run", fake_run)

    proj = tmp_path
    (proj / "build").mkdir()
    (proj / "images").mkdir()
    (proj / "config.yaml").write_text("title: T\nvideo:\n  resolution: 1080p\n  fps: 60\n")

    chapter = {
        "id": "intro", "title": "I", "narration": "hi",
        "scene_type": "manim", "images": [], "duration_estimate": 2.0,
    }
    out = render_mod.render_chapter(proj, chapter, "T", 2.0)

    # Output path should be in build/frames/, not build/clips/
    assert "/build/frames/" in out, f"output path {out} should be under build/frames/"
    assert "/build/clips/" not in out
    assert (proj / "build" / "frames" / "intro.mp4").exists()
    assert not (proj / "build" / "clips" / "intro.mp4").exists()
