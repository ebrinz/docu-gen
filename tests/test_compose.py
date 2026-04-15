# tests/test_compose.py
import pytest
from docugen.renderers import register_renderer, get_renderer, RENDERERS


def test_register_and_retrieve_renderer():
    def dummy(node, inputs, clip, project_path):
        return project_path / "out.mp4"

    register_renderer("test_dummy", dummy)
    assert get_renderer("test_dummy") is dummy


def test_get_unknown_renderer_raises():
    with pytest.raises(KeyError, match="no_such_renderer"):
        get_renderer("no_such_renderer")


def test_registry_rejects_non_callable():
    with pytest.raises(TypeError):
        register_renderer("bad", "not_a_function")


from pathlib import Path
from docugen.compose import topo_sort, content_hash, render_clip_dag


def test_topo_sort_linear():
    nodes = [
        {"name": "bg", "renderer": "manim_theme"},
        {"name": "choreo", "renderer": "manim_choreo", "refs": ["bg"]},
        {"name": "composite", "renderer": "ffmpeg_composite", "inputs": ["bg", "choreo"]},
    ]
    order = topo_sort(nodes)
    names = [n["name"] for n in order]
    assert names.index("bg") < names.index("choreo")
    assert names.index("choreo") < names.index("composite")


def test_topo_sort_detects_cycle():
    nodes = [
        {"name": "a", "renderer": "x", "refs": ["b"]},
        {"name": "b", "renderer": "x", "refs": ["a"]},
    ]
    with pytest.raises(ValueError, match="cycle"):
        topo_sort(nodes)


def test_content_hash_stable():
    node = {"name": "bg", "renderer": "manim_theme", "elements": ["hex_grid"]}
    clip = {"clip_id": "intro_01", "text": "hello"}
    h1 = content_hash(node, clip, input_hashes={})
    h2 = content_hash(node, clip, input_hashes={})
    assert h1 == h2


def test_content_hash_changes_on_node_change():
    clip = {"clip_id": "intro_01", "text": "hello"}
    h1 = content_hash({"name": "bg", "renderer": "manim_theme", "elements": ["hex_grid"]},
                       clip, input_hashes={})
    h2 = content_hash({"name": "bg", "renderer": "manim_theme", "elements": ["hex_grid", "particles"]},
                       clip, input_hashes={})
    assert h1 != h2


from unittest.mock import patch, MagicMock
from docugen.renderers.manim_fused import build_fused_script


def test_build_fused_script_has_layers():
    clip = {
        "clip_id": "intro_01",
        "text": "hello world",
        "word_times": [{"word": "hello", "start": 0.0, "end": 0.5},
                       {"word": "world", "start": 0.5, "end": 1.0}],
        "visuals": {
            "slide_type": "data_text",
            "cue_words": [{"event": "show_text", "at_index": 0,
                           "params": {"text": "Hello World"}}],
            "assets": [],
        },
        "timing": {"clip_duration": 5.0},
    }
    nodes = [
        {"name": "bg", "renderer": "manim_theme",
         "elements": ["hex_grid", "imperial_border", "floating_bg"]},
        {"name": "choreo", "renderer": "manim_choreo", "refs": ["bg"]},
    ]
    from docugen.themes import load_theme
    theme = load_theme("biopunk")
    script = build_fused_script(nodes, clip, "/fake/images", theme, duration=5.0)

    assert "class Scene_intro_01" in script
    assert "self.layers" in script
    assert "make_hex_grid" in script
    assert "def construct" in script


def test_build_fused_script_with_content():
    clip = {
        "clip_id": "ch8_01",
        "text": "the sponge",
        "word_times": [{"word": "the", "start": 0.0, "end": 0.3},
                       {"word": "sponge", "start": 0.3, "end": 0.8}],
        "visuals": {
            "slide_type": "photo_organism",
            "cue_words": [{"event": "show_photo", "at_index": 1, "params": {}}],
            "assets": ["sponge.jpg"],
            "layout": "left",
        },
        "timing": {"clip_duration": 8.0},
    }
    nodes = [
        {"name": "bg", "renderer": "manim_theme",
         "elements": ["hex_grid", "imperial_border", "floating_bg"]},
        {"name": "content", "renderer": "static_asset",
         "asset": "sponge.jpg", "layout": "left"},
        {"name": "choreo", "renderer": "manim_choreo", "refs": ["bg", "content"]},
    ]
    from docugen.themes import load_theme
    theme = load_theme("biopunk")
    script = build_fused_script(nodes, clip, "/fake/images", theme, duration=8.0)

    assert "self.layers" in script
    assert "self.layers['content']" in script
    assert "sponge.jpg" in script


def test_biopunk_choreo_counter_uses_word_times():
    from docugen.themes import load_theme
    theme = load_theme("biopunk")
    clip = {
        "clip_id": "intro_02",
        "text": "We found four hundred twenty compounds",
        "word_times": [
            {"word": "We", "start": 0.0, "end": 0.3},
            {"word": "found", "start": 0.3, "end": 0.6},
            {"word": "four", "start": 0.6, "end": 0.9},
            {"word": "hundred", "start": 0.9, "end": 1.2},
            {"word": "twenty", "start": 1.2, "end": 1.5},
            {"word": "compounds", "start": 1.5, "end": 2.0},
        ],
        "visuals": {
            "slide_type": "counter_sync",
            "cue_words": [
                {"event": "start_count", "at_index": 2,
                 "params": {"to": 420, "color": "gold", "label": "compounds"}},
            ],
            "assets": [],
        },
    }
    code = theme.render_choreography(clip, 5.0, "/fake")
    assert "0.6" in code or "self.wait" in code
    assert "420" in code


def test_biopunk_choreo_data_text_multiline():
    from docugen.themes import load_theme
    theme = load_theme("biopunk")
    clip = {
        "clip_id": "intro_03",
        "text": "one compound two billion ten years",
        "word_times": [
            {"word": "one", "start": 0.0, "end": 0.3},
            {"word": "compound", "start": 0.3, "end": 0.7},
            {"word": "two", "start": 0.7, "end": 1.0},
            {"word": "billion", "start": 1.0, "end": 1.3},
            {"word": "ten", "start": 1.3, "end": 1.6},
            {"word": "years", "start": 1.6, "end": 2.0},
        ],
        "visuals": {
            "slide_type": "data_text",
            "cue_words": [
                {"event": "show_text", "at_index": 0,
                 "params": {"text": "1 compound \u00b7 $2B \u00b7 10 years"}},
            ],
            "assets": [],
        },
    }
    code = theme.render_choreography(clip, 5.0, "/fake")
    assert "1 compound" in code or "item_" in code


def test_biopunk_choreo_organism_uses_layers():
    from docugen.themes import load_theme
    theme = load_theme("biopunk")
    clip = {
        "clip_id": "ch8_01",
        "text": "the sponge produces compounds",
        "word_times": [
            {"word": "the", "start": 0.0, "end": 0.2},
            {"word": "sponge", "start": 0.2, "end": 0.6},
            {"word": "produces", "start": 0.6, "end": 1.0},
            {"word": "compounds", "start": 1.0, "end": 1.5},
        ],
        "visuals": {
            "slide_type": "photo_organism",
            "cue_words": [
                {"event": "show_name", "at_index": 1,
                 "params": {"name": "Haliclona"}},
            ],
            "assets": ["sponge.jpg"],
            "layout": "left",
        },
    }
    code = theme.render_choreography(clip, 8.0, "/fake")
    assert "self.layers" in code
    assert "Haliclona" in code


def test_static_asset_registered():
    from docugen.renderers import discover_renderers, get_renderer
    discover_renderers()
    fn = get_renderer("static_asset")
    assert callable(fn)

def test_audio_synth_registered():
    from docugen.renderers import discover_renderers, get_renderer
    discover_renderers()
    fn = get_renderer("audio_synth")
    assert callable(fn)

def test_ffmpeg_composite_registered():
    from docugen.renderers import discover_renderers, get_renderer
    discover_renderers()
    fn = get_renderer("ffmpeg_composite")
    assert callable(fn)

def test_ffmpeg_post_registered():
    from docugen.renderers import discover_renderers, get_renderer
    discover_renderers()
    fn = get_renderer("ffmpeg_post")
    assert callable(fn)
