"""Tests for spot tool — audio cue sheet generation."""
import pytest
from docugen.spot import build_cue_sheet, _compute_global_offsets


@pytest.fixture
def clips_data():
    return {
        "chapters": [{
            "id": "ch1",
            "clips": [
                {
                    "clip_id": "ch1_01",
                    "word_times": [],
                    "timing": {"clip_duration": 3.0},
                    "visuals": {"slide_type": "chapter_card", "cue_words": []},
                },
                {
                    "clip_id": "ch1_02",
                    "word_times": [
                        {"word": "Worth", "start": 0.0, "end": 0.3},
                        {"word": "420", "start": 0.3, "end": 0.8},
                        {"word": "billion", "start": 0.8, "end": 1.2},
                    ],
                    "timing": {"clip_duration": 3.5},
                    "visuals": {
                        "slide_type": "counter_sync",
                        "cue_words": [
                            {"word": "billion", "at_index": 2, "event": "start_count",
                             "params": {"to": 420}},
                        ],
                    },
                },
            ],
        }],
    }


def test_global_offsets(clips_data):
    offsets = _compute_global_offsets(clips_data)
    assert offsets["ch1_01"] == 0.0
    assert offsets["ch1_02"] == 3.0  # after ch1_01's 3.0s duration


def test_cue_sheet_generates_spans(clips_data):
    spans = build_cue_sheet(clips_data)
    assert len(spans) > 0
    # counter_sync has tick_accelerate + sting spans triggered by start_count
    audio_types = {s["audio"] for s in spans}
    assert "tick_accelerate" in audio_types
    assert "sting" in audio_types


def test_span_times_are_global(clips_data):
    spans = build_cue_sheet(clips_data)
    # ch1_02 starts at 3.0s, start_count cue is at word_times[2].start = 0.8s
    # So global time for start_count = 3.0 + 0.8 = 3.8
    tick_span = next(s for s in spans if s["audio"] == "tick_accelerate")
    assert tick_span["start"] == pytest.approx(3.8, abs=0.01)


def test_no_cue_words_produces_empty_sheet():
    clips_data = {
        "chapters": [{
            "id": "ch1",
            "clips": [{
                "clip_id": "ch1_01",
                "word_times": [],
                "timing": {"clip_duration": 3.0},
                "visuals": {"slide_type": "ambient_field", "cue_words": []},
            }],
        }],
    }
    spans = build_cue_sheet(clips_data)
    assert spans == []


def test_spans_sorted_by_start_time(clips_data):
    spans = build_cue_sheet(clips_data)
    for i in range(len(spans) - 1):
        assert spans[i]["start"] <= spans[i + 1]["start"]
