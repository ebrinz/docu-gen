"""Tests for title slide scene builder."""
from pathlib import Path
import pytest
from docugen.tools.title import build_title_script


@pytest.fixture
def base_colors():
    return {
        "bg": "#0a0e27",
        "accent_gold": "#f59e0b",
        "accent_cyan": "#22d3ee",
        "text": "#e2e8f0",
    }


def test_particle_reveal_generates_valid_manim(base_colors):
    script = build_title_script(
        title="PARSE-EVOL", subtitle="From a yeast paper to 64,659 compounds",
        reveal_style="particle", duration=8.0, colors=base_colors,
        font_dir="/fake/fonts",
    )
    assert "class Scene_title" in script
    assert "PARSE-EVOL" in script
    assert "from manim import" in script


def test_glitch_reveal(base_colors):
    script = build_title_script(
        title="PARSE-EVOL", subtitle="subtitle",
        reveal_style="glitch", duration=6.0, colors=base_colors,
        font_dir="/fake/fonts",
    )
    assert "class Scene_title" in script


def test_trace_reveal(base_colors):
    script = build_title_script(
        title="PARSE-EVOL", subtitle="subtitle",
        reveal_style="trace", duration=6.0, colors=base_colors,
        font_dir="/fake/fonts",
    )
    assert "DrawBorderThenFill" in script or "Write" in script


def test_typewriter_reveal(base_colors):
    script = build_title_script(
        title="PARSE-EVOL", subtitle="subtitle",
        reveal_style="typewriter", duration=6.0, colors=base_colors,
        font_dir="/fake/fonts",
    )
    assert "class Scene_title" in script


def test_unknown_style_falls_back_to_particle(base_colors):
    script = build_title_script(
        title="PARSE-EVOL", subtitle="subtitle",
        reveal_style="unknown_style", duration=6.0, colors=base_colors,
        font_dir="/fake/fonts",
    )
    assert "class Scene_title" in script


def test_generate_title_writes_to_build_title_mp4(tmp_path, monkeypatch):
    """Title output must land at build/title.mp4, not build/clips/intro_01.mp4."""
    from docugen.tools import title as title_mod

    proj = tmp_path
    (proj / "build").mkdir()
    (proj / "config.yaml").write_text("title: T\n")
    (proj / "build" / "plan.json").write_text(
        '{"title":"T","chapters":[{"id":"intro","title":"I","narration":"hi",'
        '"scene_type":"manim","images":[],"duration_estimate":2.0}]}'
    )

    def fake_run(cmd, *args, **kwargs):
        class Result:
            returncode = 0
            stdout = b""
            stderr = b""
        # Simulate manim's output: find --media_dir arg and write a placeholder MP4
        for i, token in enumerate(cmd):
            if token == "--media_dir":
                media_dir = Path(cmd[i + 1])
                target = media_dir / "videos" / "_scene_title" / "1080p60" / "Scene_title.mp4"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"fake")
        return Result()

    monkeypatch.setattr("subprocess.run", fake_run)
    title_mod.generate_title(proj, duration=2.0)

    assert (proj / "build" / "title.mp4").exists()
    # Old path must no longer be produced
    assert not (proj / "build" / "clips" / "intro_01.mp4").exists()
