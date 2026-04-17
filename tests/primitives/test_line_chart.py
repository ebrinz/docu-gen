import ast
from docugen.themes.primitives import line_chart
from docugen.themes.primitives._base import validate_schema


def test_metadata():
    assert line_chart.NAME == "line_chart"
    assert "draw_line" in line_chart.CUE_EVENTS


def test_schema_valid():
    data = {
        "title": "Fitness",
        "x_label": "Gen", "y_label": "Rate",
        "series": [{"label": "A",
                    "points": [[0, 0.4], [5, 0.5], [12, 0.74]],
                    "emphasized": True}],
    }
    assert validate_schema(data, line_chart.DATA_SCHEMA, "data") == []


def test_schema_rejects_bad_points_not_list():
    data = {"series": [{"label": "A", "points": "not a list"}]}
    errs = validate_schema(data, line_chart.DATA_SCHEMA, "data")
    assert any("points" in e for e in errs)


def test_render_compiles():
    clip = {"clip_id": "x", "text": "",
            "word_times": [{"word": "x", "start": 0.0, "end": 0.3}],
            "visuals": {"slide_type": "line_chart",
                        "data": {"series": [{"label": "A",
                                             "points": [[0, 0.4], [1, 0.6], [2, 0.9]]}]},
                        "cue_words": [{"event": "draw_line", "at_index": 0,
                                       "params": {}}]}}
    body = line_chart.render(clip, duration=8.0, images_dir="/tmp", theme=None)
    ast.parse("def construct(self):\n" + body)


def test_render_no_series_alive_waits():
    clip = {"clip_id": "x", "visuals": {"slide_type": "line_chart",
                                        "data": {"series": []}}}
    body = line_chart.render(clip, duration=3.0, images_dir="/tmp", theme=None)
    assert "alive_wait" in body
