import ast
from docugen.themes.primitives import before_after
from docugen.themes.primitives._base import validate_schema


def test_metadata():
    assert before_after.NAME == "before_after"
    assert "reveal_delta" in before_after.CUE_EVENTS


def test_schema_valid():
    data = {
        "metric": "turnaround",
        "before": {"value": 72, "label": "Manual", "unit": "hrs"},
        "after":  {"value": 4,  "label": "Automated", "unit": "hrs"},
        "delta_display": "pct_change",
        "direction": "lower_is_better",
    }
    assert validate_schema(data, before_after.DATA_SCHEMA, "data") == []


def test_schema_rejects_bad_delta_display():
    data = {
        "metric": "x",
        "before": {"value": 1, "label": "A"},
        "after":  {"value": 2, "label": "B"},
        "delta_display": "nonsense",
    }
    errs = validate_schema(data, before_after.DATA_SCHEMA, "data")
    assert any("delta_display" in e for e in errs)


def test_render_compiles():
    clip = {"clip_id": "x", "text": "",
            "word_times": [{"word": "x", "start": 0, "end": 0.3}],
            "visuals": {"slide_type": "before_after",
                        "data": {
                            "metric": "X",
                            "before": {"value": 72, "label": "Old"},
                            "after":  {"value": 4,  "label": "New"},
                        },
                        "cue_words": [{"event": "show_before",
                                       "at_index": 0, "params": {}}]}}
    body = before_after.render(clip, duration=6.0, images_dir="/tmp", theme=None)
    ast.parse("def construct(self):\n" + body)
