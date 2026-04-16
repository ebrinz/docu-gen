"""chapter_card — metadata + render smoke."""
import ast
from docugen.themes.primitives import chapter_card


def test_metadata():
    assert chapter_card.NAME == "chapter_card"
    assert chapter_card.CUE_EVENTS == {"reveal_number", "reveal_title"}


def test_audio_spans():
    triggers = [s["trigger"] for s in chapter_card.AUDIO_SPANS]
    assert "reveal_title" in triggers


def test_render_compiles():
    clip = {"clip_id": "ch1_01", "text": "Chapter One",
            "word_times": [], "visuals": {"slide_type": "chapter_card"}}
    body = chapter_card.render(clip, duration=3.0, images_dir="/tmp", theme=None)
    ast.parse("def construct(self):\n" + body)
