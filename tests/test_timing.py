"""Tests for timing model."""
import pytest
from docugen.timing import compute_clip_timing, compute_chapter_timeline


@pytest.fixture
def clip_with_word_times():
    return {
        "clip_id": "ch1_02",
        "text": "We screened compounds.",
        "pacing": "normal",
        "word_times": [
            {"word": "We", "start": 0.0, "end": 0.2},
            {"word": "screened", "start": 0.2, "end": 0.6},
            {"word": "compounds.", "start": 0.6, "end": 1.1},
        ],
    }


@pytest.fixture
def clip_no_narration():
    return {
        "clip_id": "ch1_01",
        "text": "",
        "pacing": "normal",
        "word_times": [],
    }


def test_timing_from_wav_and_word_times(clip_with_word_times):
    timing = compute_clip_timing(clip_with_word_times, wav_duration=1.8, chapter_offset=0.0)
    assert timing["wav_duration"] == 1.8
    assert timing["speech_start"] == 0.0
    assert timing["speech_end"] == 1.1
    assert timing["trailing_silence"] == pytest.approx(0.7, abs=0.01)
    # pacing_pad = max(0, 1.5 - 0.7) = 0.8
    assert timing["pacing_pad"] == pytest.approx(0.8, abs=0.01)
    # clip_duration = 1.8 + 0.8 = 2.6
    assert timing["clip_duration"] == pytest.approx(2.6, abs=0.01)
    assert timing["chapter_offset"] == 0.0


def test_timing_no_double_pad_when_trailing_silence_exceeds_target(clip_with_word_times):
    clip_with_word_times["word_times"][-1]["end"] = 0.5
    timing = compute_clip_timing(clip_with_word_times, wav_duration=3.0, chapter_offset=0.0)
    assert timing["trailing_silence"] == pytest.approx(2.5, abs=0.01)
    assert timing["pacing_pad"] == 0.0
    assert timing["clip_duration"] == 3.0


def test_timing_chapter_card_fixed_duration(clip_no_narration):
    timing = compute_clip_timing(clip_no_narration, wav_duration=0.0, chapter_offset=5.0)
    assert timing["clip_duration"] == 3.0
    assert timing["chapter_offset"] == 5.0


def test_timing_tight_pacing(clip_with_word_times):
    clip_with_word_times["pacing"] = "tight"
    timing = compute_clip_timing(clip_with_word_times, wav_duration=1.5, chapter_offset=0.0)
    # target_pad for tight = 0.5, trailing = 1.5 - 1.1 = 0.4, pad = max(0, 0.5-0.4) = 0.1
    assert timing["pacing_pad"] == pytest.approx(0.1, abs=0.01)


def test_timing_breathe_pacing(clip_with_word_times):
    clip_with_word_times["pacing"] = "breathe"
    timing = compute_clip_timing(clip_with_word_times, wav_duration=1.2, chapter_offset=0.0)
    # trailing = 1.2 - 1.1 = 0.1, target_pad = 3.0, pad = max(0, 3.0-0.1) = 2.9
    assert timing["pacing_pad"] == pytest.approx(2.9, abs=0.01)


def test_chapter_timeline():
    clips = [
        {"clip_id": "ch1_01", "timing": {"clip_duration": 3.0}},
        {"clip_id": "ch1_02", "timing": {"clip_duration": 5.5}},
        {"clip_id": "ch1_03", "timing": {"clip_duration": 4.2}},
    ]
    offsets = compute_chapter_timeline(clips)
    assert offsets == [0.0, 3.0, 8.5]
