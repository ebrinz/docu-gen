"""Back-compat aliases for legacy slide type names."""
from docugen.themes.slides import (
    SLIDE_REGISTRY, PRIMITIVE_ALIASES,
    validate_slide_type, validate_cue_event,
)


def test_aliases_mapped_to_new_primitives():
    assert PRIMITIVE_ALIASES["data_text"] == "callout"
    assert PRIMITIVE_ALIASES["counter_sync"] == "counter"
    assert PRIMITIVE_ALIASES["bar_chart_build"] == "bar_chart"


def test_data_text_alias_validates():
    assert validate_slide_type("data_text") is True


def test_counter_sync_alias_validates():
    assert validate_slide_type("counter_sync") is True


def test_bar_chart_build_alias_validates():
    assert validate_slide_type("bar_chart_build") is True


def test_old_cue_event_still_validates():
    # counter_sync used `start_count` — must keep working
    assert validate_cue_event("counter_sync", "start_count") is True


def test_alias_shares_target_description():
    # counter_sync's registry entry should inherit counter's description
    assert SLIDE_REGISTRY["counter_sync"]["description"] == SLIDE_REGISTRY["counter"]["description"]
