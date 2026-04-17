"""llm_custom — escape hatch. The 'render' function here is a no-op stub;
the real work happens in renderers/manim_llm_custom.py, which this primitive
declares itself compatible with via the default DAG routing."""

NAME = "llm_custom"
DESCRIPTION = "Escape hatch — raw Manim script authored by MCP client"
CUE_EVENTS: set[str] = set()
AUDIO_SPANS: list[dict] = []
DATA_SCHEMA = {
    "required": ["custom_script", "rationale"],
    "types": {"custom_script": str, "rationale": str,
              "imports": list, "est_duration_s": (int, float)},
}
PARAMS = {}
NEEDS_CONTENT = False
DEPRECATED = False
USES_CUSTOM_RENDERER = True


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    # No-op stub. If this ever gets executed via the fused-scene path,
    # we emit an alive_wait; real rendering goes through manim_llm_custom.
    return f"        alive_wait(self, {max(duration, 0.5):.2f}, particles=bg)\n"
