"""Per-primitive schema validation tests for direct_apply."""
import pytest
from docugen.direct import validate_clip_direction


@pytest.fixture
def base_clip():
    return {
        "clip_id": "ch1_01",
        "text": "Revenue grew",
        "word_times": [
            {"word": "Revenue", "start": 0.0, "end": 0.4},
            {"word": "grew", "start": 0.4, "end": 0.7},
        ],
    }


def _direction(slide_type, data=None, cue_event=None):
    return {
        "slide_type": slide_type,
        "assets": [],
        "data": data or {},
        "cue_words": [{"word": "Revenue", "at_index": 0,
                       "event": cue_event or "show_primary",
                       "params": {}}] if cue_event is not None else [],
        "layout": "center",
        "transition_in": "crossfade",
        "transition_out": "crossfade_next",
        "transition_sound": None,
    }


def test_valid_callout_passes(base_clip):
    direction = _direction("callout",
                            data={"primary": "$41"},
                            cue_event="show_primary")
    errs = validate_clip_direction(direction, base_clip, set())
    assert errs == []


def test_callout_missing_primary_rejected(base_clip):
    direction = _direction("callout",
                            data={"secondary": "X"},
                            cue_event="show_primary")
    errs = validate_clip_direction(direction, base_clip, set())
    assert any("primary" in e for e in errs)


def test_bar_chart_schema_enforced(base_clip):
    # missing required 'series'
    direction = _direction("bar_chart",
                            data={"title": "X"},
                            cue_event="show_bar")
    errs = validate_clip_direction(direction, base_clip, set())
    assert any("series" in e for e in errs)


def test_llm_custom_requires_script_and_rationale(base_clip):
    direction = _direction("llm_custom", data={}, cue_event=None)
    # no cue_events for llm_custom; drop the cue_words so the cue validator
    # doesn't error.
    direction["cue_words"] = []
    errs = validate_clip_direction(direction, base_clip, set())
    assert any("custom_script" in e for e in errs)
    assert any("rationale" in e for e in errs)


def test_alias_resolves_for_schema_validation(base_clip):
    """counter_sync (legacy name) should validate against counter's schema."""
    direction = _direction("counter_sync",
                            data={"to": 420},
                            cue_event="start_count")
    errs = validate_clip_direction(direction, base_clip, set())
    assert errs == []


def test_counter_missing_to_rejected(base_clip):
    direction = _direction("counter",
                            data={"from": 0},
                            cue_event="start_count")
    errs = validate_clip_direction(direction, base_clip, set())
    assert any("to" in e for e in errs)
