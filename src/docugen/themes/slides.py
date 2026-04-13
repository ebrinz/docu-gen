"""Slide type registry — defines available scene builders and their valid cue events.

The direct tool picks slide types from this registry. The renderer dispatches to
scene builders based on slide_type. This module is the contract between them.
"""

SLIDE_REGISTRY = {
    "title": {
        "description": "Title + subtitle with configurable reveal style",
        "events": {"reveal_title", "reveal_subtitle"},
        "params": {"reveal_style": "particle"},
    },
    "chapter_card": {
        "description": "Chapter number + title, imperial border draws in",
        "events": {"reveal_number", "reveal_title"},
        "params": {},
    },
    "svg_reveal": {
        "description": "SVG asset fades/draws in, Ken Burns drift, labels",
        "events": {"show_asset", "highlight_region", "show_label"},
        "params": {},
    },
    "photo_organism": {
        "description": "Photo inset with HUD border, animated pointer labels",
        "events": {"show_photo", "show_structure", "show_name", "show_note"},
        "params": {},
    },
    "counter_sync": {
        "description": "Number animates 0 to target, keyed to narration word",
        "events": {"start_count", "hold"},
        "params": {"to": 0, "color": "gold", "label": ""},
    },
    "bar_chart_build": {
        "description": "Horizontal bars grow in sequence, synced to list",
        "events": {"show_bar"},
        "params": {"items": []},
    },
    "before_after": {
        "description": "Side-by-side comparison with morphing values",
        "events": {"show_before", "show_after", "morph"},
        "params": {"label": "", "before": "", "after": ""},
    },
    "dot_merge": {
        "description": "Two compound dots approach and merge",
        "events": {"show_dot1", "show_dot2", "merge"},
        "params": {"dot1": "", "dot2": "", "result": ""},
    },
    "remove_reveal": {
        "description": "One compound fades, another emerges",
        "events": {"remove", "reveal"},
        "params": {"removed": "", "emerged": ""},
    },
    "data_text": {
        "description": "Key text/numbers on screen synced to narration",
        "events": {"show_text"},
        "params": {"text": ""},
    },
    "ambient_field": {
        "description": "Particle field + theme bg, no foreground content",
        "events": set(),
        "params": {},
    },
}


def validate_slide_type(slide_type: str) -> bool:
    """Check if a slide type exists in the registry."""
    return slide_type in SLIDE_REGISTRY


def validate_cue_event(slide_type: str, event: str) -> bool:
    """Check if an event is valid for a given slide type."""
    info = SLIDE_REGISTRY.get(slide_type)
    if not info:
        return False
    return event in info["events"]


def get_slide_types_prompt() -> str:
    """Format the registry as a string for inclusion in LLM prompts."""
    lines = []
    for name, info in SLIDE_REGISTRY.items():
        events = ", ".join(sorted(info["events"])) if info["events"] else "(none)"
        lines.append(f"- {name}: {info['description']}. Cue events: {events}")
    return "\n".join(lines)
