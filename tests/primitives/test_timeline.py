import ast
from docugen.themes.primitives import timeline
from docugen.themes.primitives._base import validate_schema


def test_metadata():
    assert timeline.NAME == "timeline"
    assert "reveal_event" in timeline.CUE_EVENTS


def test_schema_valid():
    data = {
        "range": {"start": "2020", "end": "2025"},
        "events": [
            {"at": "2021-Q2", "label": "Pre-seed", "marker": "dot"},
            {"at": "2023-Q1", "label": "Pilot", "marker": "star", "emphasized": True},
        ],
        "orientation": "horizontal",
    }
    assert validate_schema(data, timeline.DATA_SCHEMA, "data") == []


def test_parse_date_fractional_year():
    assert timeline._parse_at("2021-Q1") == 2021.0
    assert timeline._parse_at("2021-Q4") == 2021.75
    assert abs(timeline._parse_at("2023") - 2023.0) < 1e-9


def test_render_compiles():
    clip = {"clip_id": "x", "text": "",
            "word_times": [{"word": "x", "start": 0, "end": 0.3}],
            "visuals": {"slide_type": "timeline",
                        "data": {"range": {"start": "2020", "end": "2025"},
                                 "events": [{"at": "2022", "label": "X"}]},
                        "cue_words": [{"event": "reveal_event",
                                       "at_index": 0, "params": {}}]}}
    body = timeline.render(clip, duration=6.0, images_dir="/tmp", theme=None)
    ast.parse("def construct(self):\n" + body)


def test_render_no_events_alive_waits():
    clip = {"clip_id": "x", "visuals": {"slide_type": "timeline",
                                        "data": {"range": {"start": "2020", "end": "2025"},
                                                 "events": []}}}
    body = timeline.render(clip, duration=3.0, images_dir="/tmp", theme=None)
    assert "alive_wait" in body
