"""Tests for narrate v2 — short clip consolidation."""
import pytest
from docugen.tools.narrate import _detect_short_hot_clips, _plan_consolidation


def test_detect_short_hot_clip():
    clips = [
        {"clip_id": "ch1_02", "text": "They found two.", "exaggeration": 0.4,
         "word_times": [{"word": "They"}, {"word": "found"}, {"word": "two."}]},
    ]
    result = _detect_short_hot_clips(clips)
    assert result == [0]


def test_ignore_normal_clip():
    clips = [
        {"clip_id": "ch1_02",
         "text": "This is a perfectly normal length sentence with enough words.",
         "exaggeration": 0.2,
         "word_times": [{"word": w} for w in "This is a perfectly normal length sentence with enough words".split()]},
    ]
    result = _detect_short_hot_clips(clips)
    assert result == []


def test_ignore_short_low_exaggeration():
    clips = [
        {"clip_id": "ch1_02", "text": "Just three words.", "exaggeration": 0.15,
         "word_times": [{"word": "Just"}, {"word": "three"}, {"word": "words."}]},
    ]
    result = _detect_short_hot_clips(clips)
    assert result == []


def test_plan_consolidation_merges_with_predecessor():
    clips = [
        {"clip_id": "ch1_02", "text": "They tested two thousand compounds.",
         "exaggeration": 0.3,
         "word_times": [{"word": w} for w in "They tested two thousand compounds".split()]},
        {"clip_id": "ch1_03", "text": "Two.", "exaggeration": 0.5,
         "word_times": [{"word": "Two."}]},
    ]
    plan = _plan_consolidation(clips, [1])
    assert len(plan) == 1
    assert plan[0] == {"merge_into": 0, "short_index": 1}


def test_plan_consolidation_first_clip_merges_forward():
    clips = [
        {"clip_id": "ch1_01", "text": "Two.", "exaggeration": 0.5,
         "word_times": [{"word": "Two."}]},
        {"clip_id": "ch1_02", "text": "They tested compounds in the lab.",
         "exaggeration": 0.3,
         "word_times": [{"word": w} for w in "They tested compounds in the lab".split()]},
    ]
    plan = _plan_consolidation(clips, [0])
    assert len(plan) == 1
    assert plan[0] == {"merge_into": 1, "short_index": 0}
