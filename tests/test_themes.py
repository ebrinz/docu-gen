# tests/test_themes.py
import pytest
from docugen.themes import list_themes, load_theme


def test_list_themes_includes_biopunk():
    themes = list_themes()
    assert "biopunk" in themes


def test_load_theme_returns_theme_object():
    theme = load_theme("biopunk")
    assert theme.name == "biopunk"
    assert isinstance(theme.palette, dict)
    assert "bg" in theme.palette


def test_load_unknown_theme_raises():
    with pytest.raises(ValueError, match="Unknown theme"):
        load_theme("nonexistent")


def test_biopunk_manim_header_has_palette():
    theme = load_theme("biopunk")
    header = theme.manim_header()
    assert 'config.background_color' in header
    assert '#050510' in header
    assert 'def make_hex_grid' in header
    assert 'def alive_wait' in header


def test_biopunk_default_dag_returns_nodes():
    theme = load_theme("biopunk")
    clip = {
        "clip_id": "test_01",
        "visuals": {"slide_type": "data_text", "cue_words": [], "assets": []},
    }
    dag = theme.default_dag(clip)
    assert isinstance(dag, list)
    assert len(dag) >= 2
    names = [n["name"] for n in dag]
    assert "bg" in names
    assert "choreo" in names
    renderers = [n["renderer"] for n in dag]
    assert "manim_theme" in renderers
    assert "manim_choreo" in renderers


def test_biopunk_default_dag_includes_content_when_assets():
    theme = load_theme("biopunk")
    clip = {
        "clip_id": "test_02",
        "visuals": {
            "slide_type": "photo_organism",
            "assets": ["yeast.jpg"],
            "cue_words": [],
        },
    }
    dag = theme.default_dag(clip)
    names = [n["name"] for n in dag]
    assert "content" in names


def test_biopunk_default_dag_no_content_without_assets():
    theme = load_theme("biopunk")
    clip = {
        "clip_id": "test_03",
        "visuals": {"slide_type": "counter_sync", "cue_words": [], "assets": []},
    }
    dag = theme.default_dag(clip)
    names = [n["name"] for n in dag]
    assert "content" not in names


def test_biopunk_transition_sounds_returns_callables():
    theme = load_theme("biopunk")
    sounds = theme.transition_sounds()
    assert isinstance(sounds, dict)
    assert len(sounds) > 0
    for name, fn in sounds.items():
        assert callable(fn)


def test_biopunk_chapter_layers_returns_callables():
    theme = load_theme("biopunk")
    layers = theme.chapter_layers()
    assert isinstance(layers, dict)
    for name, fn in layers.items():
        assert callable(fn)


def test_biopunk_dispatches_to_primitive():
    theme = load_theme("biopunk")
    clip = {
        "clip_id": "x", "text": "hello",
        "word_times": [{"word": "hello", "start": 0, "end": 0.3}],
        "visuals": {"slide_type": "callout",
                    "data": {"primary": "TEST"},
                    "cue_words": [{"event": "show_primary", "at_index": 0,
                                   "params": {}}]},
    }
    body = theme.render_choreography(clip, duration=3.0, images_dir="/tmp")
    assert "TEST" in body


def test_biopunk_resolves_legacy_alias():
    """counter_sync should dispatch to counter primitive."""
    theme = load_theme("biopunk")
    clip = {
        "clip_id": "x", "text": "",
        "word_times": [{"word": "x", "start": 0, "end": 0.3}],
        "visuals": {"slide_type": "counter_sync",
                    "data": {"to": 420},
                    "cue_words": [{"event": "start_count", "at_index": 0,
                                   "params": {}}]},
    }
    body = theme.render_choreography(clip, duration=5.0, images_dir="/tmp")
    assert "tracker" in body  # counter primitive uses ValueTracker


def test_biopunk_unknown_slide_type_falls_back():
    theme = load_theme("biopunk")
    clip = {"clip_id": "x", "text": "",
            "word_times": [],
            "visuals": {"slide_type": "bogus_type", "data": {}}}
    body = theme.render_choreography(clip, duration=3.0, images_dir="/tmp")
    # Fallback should produce an alive_wait hold, not a crash
    assert "alive_wait" in body
