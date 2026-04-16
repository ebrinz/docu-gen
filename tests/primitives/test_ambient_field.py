"""ambient_field — decorative background, no cue events."""
import ast
from docugen.themes.primitives import ambient_field


def test_metadata():
    assert ambient_field.NAME == "ambient_field"
    assert ambient_field.CUE_EVENTS == set()
    assert ambient_field.AUDIO_SPANS == []


def test_render_is_valid_wait():
    clip = {"clip_id": "x", "visuals": {}, "text": "", "word_times": []}
    body = ambient_field.render(clip, duration=4.0, images_dir="/tmp", theme=None)
    ast.parse("def construct(self):\n" + body)
    assert "wait" in body.lower()
