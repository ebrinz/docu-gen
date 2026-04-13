"""Tests for title slide scene builder."""
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
