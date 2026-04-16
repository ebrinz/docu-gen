import ast
from docugen.themes.primitives import callout
from docugen.themes.primitives._base import validate_schema


def test_metadata():
    assert callout.NAME == "callout"
    assert "show_primary" in callout.CUE_EVENTS


def test_schema_accepts_valid():
    data = {"primary": "$41", "secondary": "BOM", "style": "headline"}
    assert validate_schema(data, callout.DATA_SCHEMA, "data") == []


def test_schema_rejects_bad_style():
    errs = validate_schema(
        {"primary": "X", "style": "bogus"}, callout.DATA_SCHEMA, "data")
    assert any("style" in e for e in errs)


def test_render_compiles():
    clip = {"clip_id": "x", "text": "",
            "word_times": [{"word": "x", "start": 0.0, "end": 0.5}],
            "visuals": {"slide_type": "callout",
                        "data": {"primary": "$41", "secondary": "BOM"},
                        "cue_words": [{"event": "show_primary", "at_index": 0,
                                       "params": {}}]}}
    body = callout.render(clip, duration=3.0, images_dir="/tmp", theme=None)
    ast.parse("def construct(self):\n" + body)
