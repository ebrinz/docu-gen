"""counter — number counts up from/to with formatting, suffix, easing."""

NAME = "counter"
DESCRIPTION = "Number animates from->to, keyed to narration, units + context"
CUE_EVENTS = {"start_count", "hold", "reveal_context"}
AUDIO_SPANS = [
    {"trigger": "start_count", "offset": 0.0, "duration": 2.5,
     "audio": "tick_accelerate", "curve": "ramp_up"},
    {"trigger": "start_count", "offset": 2.5, "duration": 0.4,
     "audio": "sting", "curve": "spike"},
]
DATA_SCHEMA = {
    "required": ["to"],
    "types": {"from": (int, float), "to": (int, float),
              "format": str, "suffix": str, "context_label": str,
              "duration_s": (int, float), "easing": str},
    "enums": {"easing": {"linear", "ease_out_cubic", "ease_in_cubic",
                         "ease_in_out_cubic"}},
}
PARAMS = {}
NEEDS_CONTENT = False
DEPRECATED = False


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    visuals = clip.get("visuals", {})
    data = visuals.get("data") or {}
    start = data.get("from", 0)
    end = data["to"]
    fmt = data.get("format", "{:,.0f}")
    suffix = data.get("suffix", "")
    context = data.get("context_label", "")
    count_dur = float(data.get("duration_s", 2.5))

    hold = max(duration - count_dur - 1.0, 0.5)

    lines = [
        f'        from_val = {start}\n',
        f'        to_val = {end}\n',
        f'        tracker = ValueTracker(from_val)\n',
        f'        label = always_redraw(\n',
        f'            lambda: Text(\n'
        f'                ({fmt!r}).format(tracker.get_value()) + {suffix!r},\n'
        f'                font="Courier", weight=BOLD).scale(1.4)\n'
        f'        )\n',
        f'        self.add(label)\n',
        f'        self.play(tracker.animate.set_value(to_val),\n'
        f'                  run_time={count_dur:.2f}, rate_func=rush_from)\n',
    ]
    if context:
        ctx = context.replace('"', '\\"')
        lines.append(
            f'        ctx = Text("{ctx}", font="Courier", color=TEXT_DIM).scale(0.5)\n'
            f'        ctx.next_to(label, DOWN, buff=0.4)\n'
            f'        self.play(FadeIn(ctx), run_time=0.5)\n'
        )
    lines.append(f'        alive_wait(self, {hold:.2f}, particles=bg)\n')
    return "".join(lines)
