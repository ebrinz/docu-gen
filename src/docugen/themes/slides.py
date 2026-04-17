"""Slide type registry — auto-populated from docugen.themes.primitives.

The direct tool picks slide types from this registry. The renderer dispatches
to primitive modules based on slide_type. The spot tool uses span patterns to
build the audio cue sheet.
"""

from docugen.themes.primitives import discover_primitives

INTENSITY_CURVES = {
    "ramp_up", "ramp_down", "spike", "sustain", "ease_in", "linear",
}

AUDIO_TREATMENTS = {
    "hit", "tension_build", "sweep_tone", "tick_accelerate", "sting",
    "swoosh", "blip", "swell_hit", "trace_hum", "tick", "morph_tone",
    "fade_down", "rise",
}


def _build_registry() -> dict:
    reg: dict = {}
    for name, mod in discover_primitives().items():
        reg[name] = {
            "description": mod.DESCRIPTION,
            "events": set(mod.CUE_EVENTS),
            "params": dict(getattr(mod, "PARAMS", {})),
            "spans": list(mod.AUDIO_SPANS),
            "needs_content": bool(getattr(mod, "NEEDS_CONTENT", False)),
            "deprecated": bool(getattr(mod, "DEPRECATED", False)),
        }
    return reg


SLIDE_REGISTRY = _build_registry()


def validate_slide_type(slide_type: str) -> bool:
    return slide_type in SLIDE_REGISTRY


def validate_cue_event(slide_type: str, event: str) -> bool:
    info = SLIDE_REGISTRY.get(slide_type)
    if not info:
        return False
    return event in info["events"]


def get_slide_types_prompt() -> str:
    lines = []
    for name, info in SLIDE_REGISTRY.items():
        events = ", ".join(sorted(info["events"])) if info["events"] else "(none)"
        prefix = "[DEPRECATED] " if info.get("deprecated") else ""
        lines.append(f"- {name}: {prefix}{info['description']}. Cue events: {events}")
    return "\n".join(lines)
