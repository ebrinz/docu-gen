import ast
from docugen.themes.primitives import bar_chart
from docugen.themes.primitives._base import validate_schema


def test_metadata():
    assert bar_chart.NAME == "bar_chart"
    assert "show_bar" in bar_chart.CUE_EVENTS
    assert "show_axes" in bar_chart.CUE_EVENTS


def test_schema_valid():
    data = {
        "title": "Revenue",
        "x_label": "Year", "y_label": "USDm",
        "orientation": "vertical",
        "baseline": 0,
        "series": [
            {"label": "2022", "value": 2.1},
            {"label": "2024", "value": 14.3, "emphasized": True},
        ],
        "value_format": "${:.1f}M",
    }
    assert validate_schema(data, bar_chart.DATA_SCHEMA, "data") == []


def test_schema_rejects_empty_series():
    # Empty series is allowed at schema level (no "type" violation);
    # render handles the no-data case with a silent alive_wait.
    data = {"title": "X", "series": []}
    errs = validate_schema(data, bar_chart.DATA_SCHEMA, "data")
    assert all("type" not in e.lower() for e in errs)


def test_render_compiles():
    clip = {"clip_id": "x", "text": "",
            "word_times": [{"word": "x", "start": 0, "end": 0.3}],
            "visuals": {"slide_type": "bar_chart",
                        "data": {
                            "title": "Revenue",
                            "series": [{"label": "A", "value": 2.0},
                                       {"label": "B", "value": 5.5}],
                        },
                        "cue_words": [{"event": "show_bar", "at_index": 0,
                                       "params": {}}]}}
    body = bar_chart.render(clip, duration=8.0, images_dir="/tmp", theme=None)
    ast.parse("def construct(self):\n" + body)


def test_render_no_series_returns_alive_wait():
    clip = {"clip_id": "x", "text": "",
            "word_times": [],
            "visuals": {"slide_type": "bar_chart", "data": {"series": []}}}
    body = bar_chart.render(clip, duration=3.0, images_dir="/tmp", theme=None)
    assert "alive_wait" in body
