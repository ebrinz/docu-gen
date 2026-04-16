import ast
from docugen.themes.primitives import svg_reveal


def test_metadata():
    assert svg_reveal.NAME == "svg_reveal"
    assert "show_asset" in svg_reveal.CUE_EVENTS
    assert svg_reveal.NEEDS_CONTENT is True


def test_render_compiles_with_asset():
    clip = {
        "clip_id": "x", "text": "diagram",
        "word_times": [{"word": "diagram", "start": 0.0, "end": 0.5}],
        "visuals": {
            "slide_type": "svg_reveal",
            "assets": ["diagram.svg"],
            "cue_words": [{"event": "show_asset", "at_index": 0, "params": {}}],
        },
    }
    body = svg_reveal.render(clip, duration=5.0, images_dir="/tmp", theme=None)
    ast.parse("def construct(self):\n" + body)
