"""Slide type registry — defines available scene builders, cue events, and audio spans.

The direct tool picks slide types from this registry. The renderer dispatches to
scene builders based on slide_type. The spot tool uses span patterns to build
the audio cue sheet. This module is the contract between all three.
"""

# Intensity curves for audio spans
# Each describes how audio intensity shapes over a span's duration
INTENSITY_CURVES = {
    "ramp_up",      # Quiet → loud (convergence, tension build)
    "ramp_down",    # Loud → quiet (fade outs, dissolves)
    "spike",        # Silent → loud → silent (flash, hit, impact)
    "sustain",      # Hold steady (pointer drawing, scanline sweep)
    "ease_in",      # Slow start → full (photo reveals, bar growth)
    "linear",       # Even across span (scanning, sweeping)
}

# Audio treatment types — what the score engine synthesizes for each span
AUDIO_TREATMENTS = {
    "hit",              # Percussive impact, gold bell
    "tension_build",    # Filtered noise swell with rising cutoff
    "sweep_tone",       # Gliding frequency sweep
    "tick_accelerate",  # Clicks with decreasing interval
    "sting",            # Short harmonic burst
    "swoosh",           # Soft reveal whoosh
    "blip",             # Short data blip
    "swell_hit",        # Harmonic swell into impact
    "trace_hum",        # Sustained sine at theme frequency
    "tick",             # Single tick
    "morph_tone",       # Gliding pitch shift
    "fade_down",        # Descending tone
    "rise",             # Ascending tone
}

SLIDE_REGISTRY = {
    "title": {
        "description": "Title + subtitle with configurable reveal style",
        "events": {"reveal_title", "reveal_subtitle"},
        "params": {"reveal_style": "particle"},
        "spans": [
            {"trigger": "reveal_title", "offset": -2.0, "duration": 2.0,
             "audio": "tension_build", "curve": "ramp_up"},
            {"trigger": "reveal_title", "offset": 0.0, "duration": 0.3,
             "audio": "hit", "curve": "spike"},
            {"trigger": "reveal_subtitle", "offset": 0.0, "duration": 1.2,
             "audio": "sweep_tone", "curve": "linear"},
        ],
    },
    "chapter_card": {
        "description": "Chapter number + title, imperial border draws in",
        "events": {"reveal_number", "reveal_title"},
        "params": {},
        "spans": [
            {"trigger": "reveal_title", "offset": -0.5, "duration": 0.8,
             "audio": "swoosh", "curve": "ease_in"},
        ],
    },
    "svg_reveal": {
        "description": "SVG asset fades/draws in, Ken Burns drift, labels",
        "events": {"show_asset", "highlight_region", "show_label"},
        "params": {},
        "spans": [
            {"trigger": "show_asset", "offset": 0.0, "duration": 1.0,
             "audio": "swoosh", "curve": "ease_in"},
            {"trigger": "show_label", "offset": 0.0, "duration": 0.3,
             "audio": "blip", "curve": "spike"},
        ],
    },
    "photo_organism": {
        "description": "Photo inset with HUD border, animated pointer labels",
        "events": {"show_photo", "show_structure", "show_name", "show_note"},
        "params": {},
        "spans": [
            {"trigger": "show_photo", "offset": 0.0, "duration": 1.2,
             "audio": "swoosh", "curve": "ease_in"},
            {"trigger": "show_name", "offset": 0.0, "duration": 0.8,
             "audio": "trace_hum", "curve": "sustain"},
            {"trigger": "show_structure", "offset": 0.0, "duration": 0.8,
             "audio": "trace_hum", "curve": "sustain"},
            {"trigger": "show_note", "offset": 0.0, "duration": 0.3,
             "audio": "blip", "curve": "spike"},
        ],
    },
    "counter_sync": {
        "description": "Number animates 0 to target, keyed to narration word",
        "events": {"start_count", "hold"},
        "params": {"to": 0, "color": "gold", "label": ""},
        "spans": [
            {"trigger": "start_count", "offset": 0.0, "duration": 2.5,
             "audio": "tick_accelerate", "curve": "ramp_up"},
            {"trigger": "start_count", "offset": 2.5, "duration": 0.4,
             "audio": "sting", "curve": "spike"},
        ],
    },
    "bar_chart_build": {
        "description": "Horizontal bars grow in sequence, synced to list",
        "events": {"show_bar"},
        "params": {"items": []},
        "spans": [
            {"trigger": "show_bar", "offset": 0.0, "duration": 0.6,
             "audio": "tick", "curve": "ease_in"},
        ],
    },
    "before_after": {
        "description": "Side-by-side comparison with morphing values",
        "events": {"show_before", "show_after", "morph"},
        "params": {"label": "", "before": "", "after": ""},
        "spans": [
            {"trigger": "show_before", "offset": 0.0, "duration": 0.5,
             "audio": "blip", "curve": "spike"},
            {"trigger": "show_after", "offset": 0.0, "duration": 0.5,
             "audio": "blip", "curve": "spike"},
            {"trigger": "morph", "offset": 0.0, "duration": 1.5,
             "audio": "morph_tone", "curve": "linear"},
        ],
    },
    "dot_merge": {
        "description": "Two compound dots approach and merge",
        "events": {"show_dot1", "show_dot2", "merge"},
        "params": {"dot1": "", "dot2": "", "result": ""},
        "spans": [
            {"trigger": "show_dot1", "offset": 0.0, "duration": 0.3,
             "audio": "blip", "curve": "spike"},
            {"trigger": "show_dot2", "offset": 0.0, "duration": 0.3,
             "audio": "blip", "curve": "spike"},
            {"trigger": "merge", "offset": -1.5, "duration": 1.5,
             "audio": "tension_build", "curve": "ramp_up"},
            {"trigger": "merge", "offset": 0.0, "duration": 0.4,
             "audio": "swell_hit", "curve": "spike"},
        ],
    },
    "remove_reveal": {
        "description": "One compound fades, another emerges",
        "events": {"remove", "reveal"},
        "params": {"removed": "", "emerged": ""},
        "spans": [
            {"trigger": "remove", "offset": 0.0, "duration": 1.0,
             "audio": "fade_down", "curve": "ramp_down"},
            {"trigger": "reveal", "offset": 0.0, "duration": 0.8,
             "audio": "rise", "curve": "ramp_up"},
        ],
    },
    "data_text": {
        "description": "Key text/numbers on screen synced to narration",
        "events": {"show_text"},
        "params": {"text": ""},
        "spans": [
            {"trigger": "show_text", "offset": 0.0, "duration": 0.3,
             "audio": "blip", "curve": "spike"},
        ],
    },
    "ambient_field": {
        "description": "Particle field + theme bg, no foreground content",
        "events": set(),
        "params": {},
        "spans": [],
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
