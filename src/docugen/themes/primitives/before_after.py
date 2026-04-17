"""before_after — side-by-side with auto-computed delta."""

NAME = "before_after"
DESCRIPTION = "Side-by-side comparison with auto delta and direction color"
CUE_EVENTS = {"show_before", "show_after", "reveal_delta"}
AUDIO_SPANS = [
    {"trigger": "show_before", "offset": 0.0, "duration": 0.5,
     "audio": "blip", "curve": "spike"},
    {"trigger": "show_after", "offset": 0.0, "duration": 0.5,
     "audio": "blip", "curve": "spike"},
    {"trigger": "reveal_delta", "offset": 0.0, "duration": 1.5,
     "audio": "morph_tone", "curve": "linear"},
]
DATA_SCHEMA = {
    "required": ["metric", "before", "after"],
    "types": {"metric": str, "before": dict, "after": dict,
              "delta_display": str, "direction": str},
    "enums": {
        "delta_display": {"pct_change", "ratio", "absolute"},
        "direction": {"lower_is_better", "higher_is_better"},
    },
    "children": {
        "before": {"required": ["value", "label"],
                   "types": {"value": (int, float), "label": str, "unit": str}},
        "after":  {"required": ["value", "label"],
                   "types": {"value": (int, float), "label": str, "unit": str}},
    },
}
PARAMS = {}
NEEDS_CONTENT = False
DEPRECATED = False


def _compute_delta(before_v, after_v, display, direction):
    if display == "ratio":
        if after_v == 0 or before_v == 0:
            return "0×"
        return f"{max(before_v, after_v) / min(before_v, after_v):.1f}×"
    if display == "absolute":
        return f"{after_v - before_v:+.1f}"
    if before_v == 0:
        return "n/a"
    pct = (after_v - before_v) / before_v * 100.0
    return f"{pct:+.0f}%"


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    visuals = clip.get("visuals", {})
    data = visuals.get("data") or {}
    metric = data.get("metric", "").replace('"', '\\"')
    before = data.get("before", {})
    after = data.get("after", {})
    display = data.get("delta_display", "pct_change")
    direction = data.get("direction", "higher_is_better")

    bv = before.get("value", 0)
    av = after.get("value", 0)
    delta_str = _compute_delta(bv, av, display, direction)

    improving = (
        (direction == "higher_is_better" and av > bv) or
        (direction == "lower_is_better" and av < bv)
    )
    delta_color = "GLOW" if improving else "SITH_RED"

    bu = before.get("unit", "")
    au = after.get("unit", "")
    bl = before.get("label", "").replace('"', '\\"')
    al = after.get("label", "").replace('"', '\\"')

    hold = max(duration - 4.0, 0.5)
    return (
        f'        header = Text("{metric}", font="Courier", weight=BOLD).scale(0.5).to_edge(UP, buff=0.8)\n'
        f'        self.play(FadeIn(header), run_time=0.4)\n'
        f'        bl = Text("{bl}", font="Courier", color=TEXT_DIM).scale(0.4).move_to(LEFT * 3 + UP * 1.0)\n'
        f'        bv = Text("{bv}{bu}", font="Courier", weight=BOLD).scale(1.1).move_to(LEFT * 3)\n'
        f'        self.play(FadeIn(bl), FadeIn(bv), run_time=0.6)\n'
        f'        arrow = Arrow(LEFT * 1.2, RIGHT * 1.2, color={delta_color}, stroke_width=4)\n'
        f'        self.play(GrowArrow(arrow), run_time=0.6)\n'
        f'        al = Text("{al}", font="Courier", color={delta_color}).scale(0.4).move_to(RIGHT * 3 + UP * 1.0)\n'
        f'        av = Text("{av}{au}", font="Courier", color={delta_color}, weight=BOLD).scale(1.1).move_to(RIGHT * 3)\n'
        f'        self.play(FadeIn(al), FadeIn(av, scale=1.2), run_time=0.8)\n'
        f'        delta = Text("{delta_str}", font="Courier", color={delta_color}, weight=BOLD).scale(0.7)\n'
        f'        delta.next_to(arrow, DOWN, buff=0.4)\n'
        f'        self.play(FadeIn(delta, shift=UP * 0.2), run_time=0.6)\n'
        f'        alive_wait(self, {hold:.2f}, particles=bg)\n'
    )
