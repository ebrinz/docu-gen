"""title primitive — metadata + render smoke test."""
import ast
from docugen.themes.primitives import title


def test_metadata():
    assert title.NAME == "title"
    assert "reveal_title" in title.CUE_EVENTS
    assert "reveal_subtitle" in title.CUE_EVENTS


def test_audio_spans_cover_reveal_title():
    triggers = {span["trigger"] for span in title.AUDIO_SPANS}
    assert "reveal_title" in triggers


def test_render_returns_compilable_snippet():
    clip = {
        "clip_id": "intro_01",
        "text": "Hello",
        "word_times": [{"word": "Hello", "start": 0.0, "end": 0.5}],
        "visuals": {"slide_type": "title", "params": {"reveal_style": "particle"}},
    }
    body = title.render(clip, duration=5.0, images_dir="/tmp", theme=None)
    assert isinstance(body, str) and body.strip()
    wrapped = "def construct(self):\n" + body
    ast.parse(wrapped)
