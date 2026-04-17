"""Slide type registry — auto-populated from primitives package."""
from docugen.themes.slides import (
    SLIDE_REGISTRY, validate_slide_type, validate_cue_event,
    get_slide_types_prompt,
)

EXPECTED_PRIMITIVES = {
    # phase 1 MVP
    "bar_chart", "counter", "before_after", "callout",
    "line_chart", "tree", "timeline", "llm_custom",
    # migrated content primitives
    "title", "chapter_card", "ambient_field", "svg_reveal", "photo_organism",
    # deprecated back-compat
    "dot_merge", "remove_reveal",
}


def test_registry_has_expected_primitives():
    assert set(SLIDE_REGISTRY.keys()) >= EXPECTED_PRIMITIVES


def test_every_entry_has_description_and_events():
    for name, info in SLIDE_REGISTRY.items():
        assert "description" in info
        assert "events" in info
        assert isinstance(info["events"], set)
        assert "spans" in info


def test_validate_slide_type_valid():
    assert validate_slide_type("line_chart") is True
    assert validate_slide_type("counter") is True


def test_validate_slide_type_invalid():
    assert validate_slide_type("nonexistent") is False


def test_validate_cue_event_valid():
    assert validate_cue_event("line_chart", "draw_line") is True
    assert validate_cue_event("tree", "reveal_root") is True


def test_validate_cue_event_invalid():
    assert validate_cue_event("line_chart", "explode") is False


def test_prompt_mentions_deprecated():
    text = get_slide_types_prompt()
    assert "DEPRECATED" in text or "deprecated" in text


def test_prompt_lists_all_primitives():
    text = get_slide_types_prompt()
    for name in EXPECTED_PRIMITIVES:
        assert name in text
