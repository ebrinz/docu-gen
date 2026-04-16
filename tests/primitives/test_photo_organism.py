import ast
from docugen.themes.primitives import photo_organism


def test_metadata():
    assert photo_organism.NAME == "photo_organism"
    assert "show_photo" in photo_organism.CUE_EVENTS
    assert photo_organism.NEEDS_CONTENT is True


def test_render_compiles():
    clip = {
        "clip_id": "x", "text": "organism",
        "word_times": [{"word": "organism", "start": 0.0, "end": 0.5}],
        "visuals": {
            "slide_type": "photo_organism", "assets": ["img.jpg"],
            "cue_words": [{"event": "show_name", "at_index": 0,
                           "params": {"name": "Bioluminescent"}}],
        },
    }
    body = photo_organism.render(clip, duration=6.0, images_dir="/tmp", theme=None)
    ast.parse("def construct(self):\n" + body)
