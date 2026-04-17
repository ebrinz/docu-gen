import ast
from docugen.themes.primitives import counter
from docugen.themes.primitives._base import validate_schema


def test_metadata():
    assert counter.NAME == "counter"
    assert "start_count" in counter.CUE_EVENTS


def test_schema_accepts_valid():
    data = {"from": 0, "to": 14300000, "format": "${:,.0f}",
            "suffix": "ARR", "duration_s": 2.5, "easing": "ease_out_cubic"}
    assert validate_schema(data, counter.DATA_SCHEMA, "data") == []


def test_schema_rejects_missing_to():
    errs = validate_schema({"from": 0}, counter.DATA_SCHEMA, "data")
    assert any("to" in e for e in errs)


def test_render_compiles():
    clip = {"clip_id": "x", "text": "", "word_times": [
        {"word": "x", "start": 0.0, "end": 0.3}],
        "visuals": {"slide_type": "counter",
                    "data": {"from": 0, "to": 420, "format": "{:d}", "suffix": "B"},
                    "cue_words": [{"event": "start_count", "at_index": 0,
                                   "params": {}}]}}
    body = counter.render(clip, duration=5.0, images_dir="/tmp", theme=None)
    ast.parse("def construct(self):\n" + body)
