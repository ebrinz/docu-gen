"""Tests for creative director validation and timing."""
import json
import pytest
from docugen.direct import validate_clip_direction, validate_all_clips


@pytest.fixture
def valid_direction():
    return {
        "slide_type": "counter_sync",
        "assets": [],
        "cue_words": [
            {"word": "billion", "at_index": 2, "event": "start_count",
             "params": {"to": 420, "color": "gold"}}
        ],
        "layout": "center",
        "transition_in": "crossfade",
        "transition_out": "crossfade_next",
        "transition_sound": None,
    }


@pytest.fixture
def clip_with_word_times():
    return {
        "clip_id": "ch1_02",
        "text": "Worth 420 billion dollars.",
        "pacing": "normal",
        "word_times": [
            {"word": "Worth", "start": 0.0, "end": 0.3},
            {"word": "420", "start": 0.3, "end": 0.8},
            {"word": "billion", "start": 0.8, "end": 1.2},
            {"word": "dollars.", "start": 1.2, "end": 1.6},
        ],
    }


@pytest.fixture
def available_assets():
    return {"01-phase-a-survival.svg", "img_sponge_aplysina.jpg"}


def test_valid_direction_passes(valid_direction, clip_with_word_times, available_assets):
    errors = validate_clip_direction(valid_direction, clip_with_word_times, available_assets)
    assert errors == []


def test_missing_field_detected(valid_direction, clip_with_word_times, available_assets):
    del valid_direction["layout"]
    errors = validate_clip_direction(valid_direction, clip_with_word_times, available_assets)
    assert any("layout" in e for e in errors)


def test_invalid_slide_type(valid_direction, clip_with_word_times, available_assets):
    valid_direction["slide_type"] = "nonexistent_type"
    errors = validate_clip_direction(valid_direction, clip_with_word_times, available_assets)
    assert any("slide_type" in e for e in errors)


def test_missing_asset(valid_direction, clip_with_word_times, available_assets):
    valid_direction["assets"] = ["nonexistent.svg"]
    errors = validate_clip_direction(valid_direction, clip_with_word_times, available_assets)
    assert any("nonexistent.svg" in e for e in errors)


def test_cue_word_index_out_of_bounds(valid_direction, clip_with_word_times, available_assets):
    valid_direction["cue_words"][0]["at_index"] = 99
    errors = validate_clip_direction(valid_direction, clip_with_word_times, available_assets)
    assert any("at_index" in e for e in errors)


def test_invalid_cue_event(valid_direction, clip_with_word_times, available_assets):
    valid_direction["cue_words"][0]["event"] = "explode"
    errors = validate_clip_direction(valid_direction, clip_with_word_times, available_assets)
    assert any("event" in e for e in errors)


def test_validate_all_clips_aggregates_errors():
    clips_data = {
        "chapters": [{
            "id": "ch1",
            "clips": [{
                "clip_id": "ch1_01",
                "text": "",
                "word_times": [],
                "visuals": {
                    "slide_type": "nonexistent",
                    "assets": [],
                    "cue_words": [],
                    "layout": "center",
                    "transition_in": "cut",
                    "transition_out": "cut",
                    "transition_sound": None,
                },
            }],
        }],
    }
    errors = validate_all_clips(clips_data, set())
    assert len(errors) > 0
    assert "ch1_01" in errors[0]
