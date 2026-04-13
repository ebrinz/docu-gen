"""Tests for slide type registry."""
import pytest
from docugen.themes.slides import SLIDE_REGISTRY, validate_slide_type, validate_cue_event


def test_registry_has_all_types():
    expected = {
        "title", "chapter_card", "svg_reveal", "photo_organism",
        "counter_sync", "bar_chart_build", "before_after",
        "dot_merge", "remove_reveal", "data_text", "ambient_field",
    }
    assert set(SLIDE_REGISTRY.keys()) == expected


def test_each_type_has_events():
    for slide_type, info in SLIDE_REGISTRY.items():
        assert "events" in info, f"{slide_type} missing events"
        assert isinstance(info["events"], set)


def test_validate_slide_type_valid():
    assert validate_slide_type("title") is True


def test_validate_slide_type_invalid():
    assert validate_slide_type("nonexistent") is False


def test_validate_cue_event_valid():
    assert validate_cue_event("title", "reveal_title") is True


def test_validate_cue_event_invalid():
    assert validate_cue_event("title", "explode") is False


def test_validate_cue_event_ambient_field_has_no_events():
    assert validate_cue_event("ambient_field", "anything") is False
