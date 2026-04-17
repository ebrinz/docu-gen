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

# Back-compat aliases for legacy slide type names. Aliases mirror their target
# primitive's registry entry so schemas, descriptions, and spans all line up —
# existing clips.json files that still use the old names continue to render
# and validate. The primitive dispatcher resolves these aliases before calling
# into themes/primitives/.
_LEGACY_CUE_EVENTS = {
    "counter_sync": {"start_count", "hold"},
    "bar_chart_build": {"show_bar"},
    "data_text": {"show_text"},
}

PRIMITIVE_ALIASES = {
    "data_text": "callout",
    "counter_sync": "counter",
    "bar_chart_build": "bar_chart",
}

for _alias, _target in PRIMITIVE_ALIASES.items():
    if _target in SLIDE_REGISTRY and _alias not in SLIDE_REGISTRY:
        SLIDE_REGISTRY[_alias] = dict(SLIDE_REGISTRY[_target])
        SLIDE_REGISTRY[_alias]["events"] = (
            set(SLIDE_REGISTRY[_alias]["events"]) |
            _LEGACY_CUE_EVENTS.get(_alias, set())
        )


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
