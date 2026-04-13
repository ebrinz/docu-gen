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
    assert isinstance(theme.font, str)


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


def test_biopunk_idle_scene_valid_manim():
    theme = load_theme("biopunk")
    script = theme.idle_scene(10.0)
    assert 'class Scene_idle' in script
    assert 'def construct' in script


def test_biopunk_chapter_card_valid_manim():
    theme = load_theme("biopunk")
    script = theme.chapter_card("01", "THE PAPER", 5.0)
    assert 'class Scene_chapter_card' in script
    assert 'THE PAPER' in script


def test_biopunk_image_reveal_valid_manim():
    theme = load_theme("biopunk")
    script = theme.image_reveal(["test.svg"], "Fade in, zoom 1.04x", 8.0, "/tmp")
    assert 'class Scene_image_reveal' in script
    assert 'test.svg' in script


def test_biopunk_data_reveal_valid_manim():
    theme = load_theme("biopunk")
    script = theme.data_reveal("Show +16.4% in gold", 5.0)
    assert 'class Scene_data_reveal' in script


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
