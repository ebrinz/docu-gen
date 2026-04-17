"""bar_chart — real axes, auto scale, value labels.

Replaces bar_chart_build. Uses Manim's Axes with auto-computed nice ticks;
emphasized bars get the theme accent color (theme-owned emphasis).
"""

NAME = "bar_chart"
DESCRIPTION = "Bars with real axes, auto-scale, value labels, optional emphasis"
CUE_EVENTS = {"show_axes", "show_bar", "highlight_bar"}
AUDIO_SPANS = [
    {"trigger": "show_axes", "offset": 0.0, "duration": 0.4,
     "audio": "swoosh", "curve": "ease_in"},
    {"trigger": "show_bar", "offset": 0.0, "duration": 0.6,
     "audio": "tick", "curve": "ease_in"},
    {"trigger": "highlight_bar", "offset": 0.0, "duration": 0.3,
     "audio": "blip", "curve": "spike"},
]
DATA_SCHEMA = {
    "required": ["series"],
    "types": {"title": str, "x_label": str, "y_label": str,
              "orientation": str, "baseline": (int, float),
              "series": list, "value_format": str},
    "enums": {"orientation": {"vertical", "horizontal"}},
    "children": {
        "series": {"required": ["label", "value"],
                    "types": {"label": str, "value": (int, float),
                              "emphasized": bool}},
    },
}
PARAMS = {}
NEEDS_CONTENT = False
DEPRECATED = False


def _nice_ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    """Pick ~n 'round' tick values spanning lo..hi."""
    import math
    if hi <= lo:
        return [lo, lo + 1]
    rng = hi - lo
    step = 10 ** math.floor(math.log10(rng / n))
    for mult in (1, 2, 2.5, 5, 10):
        s = step * mult
        if rng / s <= n:
            step = s
            break
    start = math.floor(lo / step) * step
    ticks = []
    v = start
    while v <= hi + step * 0.5:
        ticks.append(round(v, 6))
        v += step
    return ticks


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    visuals = clip.get("visuals", {})
    data = visuals.get("data") or {}
    series = data.get("series") or []
    if not series:
        return f"        alive_wait(self, {max(duration, 0.5):.2f}, particles=bg)\n"

    title = data.get("title", "").replace('"', '\\"')
    y_label = data.get("y_label", "").replace('"', '\\"')
    value_fmt = data.get("value_format", "{:.1f}")
    baseline = float(data.get("baseline", 0))

    values = [float(s["value"]) for s in series]
    vmax = max(values + [baseline])
    vmin = min(values + [baseline, 0])
    ticks = _nice_ticks(vmin, vmax)
    y_range = (ticks[0], ticks[-1], ticks[1] - ticks[0])

    bar_time = max((duration - 3.0) / max(len(series), 1), 0.3)
    chart_height = 4.0
    chart_width = 8.0

    lines: list[str] = []
    if title:
        lines.append(
            f'        title = Text("{title}", font="Courier", weight=BOLD).scale(0.5).to_edge(UP, buff=0.5)\n'
            f'        self.play(FadeIn(title), run_time=0.4)\n'
        )
    lines.append(
        f'        ax = Axes(\n'
        f'            x_range=[0, {len(series)}, 1],\n'
        f'            y_range=[{y_range[0]}, {y_range[1]}, {y_range[2]}],\n'
        f'            x_length={chart_width}, y_length={chart_height},\n'
        f'            axis_config={{"color": TEXT_DIM, "include_tip": False,\n'
        f'                          "stroke_width": 2}},\n'
        f'        ).to_edge(DOWN, buff=1.0)\n'
        f'        yt = ax.get_y_axis().add_numbers(font_size=20, color=TEXT_DIM)\n'
        f'        self.play(Create(ax), FadeIn(yt), run_time=0.7)\n'
    )
    if y_label:
        lines.append(
            f'        yl = Text("{y_label}", font="Courier", color=TEXT_DIM).scale(0.3)\n'
            f'        yl.next_to(ax.get_y_axis(), UP, buff=0.2)\n'
            f'        self.play(FadeIn(yl), run_time=0.2)\n'
        )

    for i, s in enumerate(series):
        label = str(s["label"]).replace('"', '\\"')
        val = float(s["value"])
        emph = bool(s.get("emphasized", False))
        bar_color = "GOLD" if emph else "GLOW"
        lines.append(
            f'        # bar {i}: {label}\n'
            f'        bar_{i} = Rectangle(\n'
            f'            width={chart_width/len(series) - 0.3:.2f},\n'
            f'            height=0.01,\n'
            f'            color={bar_color}, fill_color={bar_color}, fill_opacity=0.35,\n'
            f'            stroke_width=2,\n'
            f'        )\n'
            f'        bar_{i}.move_to(ax.c2p({i} + 0.5, 0), aligned_edge=DOWN)\n'
            f'        self.add(bar_{i})\n'
            f'        target_h = ax.c2p(0, {val})[1] - ax.c2p(0, 0)[1]\n'
            f'        self.play(\n'
            f'            bar_{i}.animate.stretch_to_fit_height(abs(target_h))\n'
            f'                .move_to(ax.c2p({i} + 0.5, {val/2:.4f})),\n'
            f'            run_time={bar_time:.2f}, rate_func=smooth,\n'
            f'        )\n'
            f'        lbl_{i} = Text("{label}", font="Courier", color=TEXT_DIM).scale(0.3)\n'
            f'        lbl_{i}.next_to(bar_{i}, DOWN, buff=0.15)\n'
            f'        val_{i} = Text(({value_fmt!r}).format({val}),\n'
            f'                       font="Courier", color={bar_color}, weight=BOLD).scale(0.35)\n'
            f'        val_{i}.next_to(bar_{i}, UP, buff=0.1)\n'
            f'        self.play(FadeIn(lbl_{i}), FadeIn(val_{i}), run_time=0.3)\n'
        )

    hold = max(duration - (0.7 + len(series) * (bar_time + 0.3)) - 1.0, 0.5)
    lines.append(f'        alive_wait(self, {hold:.2f}, particles=bg)\n')
    return "".join(lines)
