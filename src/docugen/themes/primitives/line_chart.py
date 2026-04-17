"""line_chart — real axes, left-to-right line draw, highlight points."""

from docugen.themes.primitives.bar_chart import _nice_ticks

NAME = "line_chart"
DESCRIPTION = "Timeseries with real axes, line draw animation, highlight points"
CUE_EVENTS = {"draw_axes", "draw_line", "highlight_point", "reveal_annotation"}
AUDIO_SPANS = [
    {"trigger": "draw_axes", "offset": 0.0, "duration": 0.5,
     "audio": "swoosh", "curve": "ease_in"},
    {"trigger": "draw_line", "offset": 0.0, "duration": 1.5,
     "audio": "trace_hum", "curve": "sustain"},
    {"trigger": "highlight_point", "offset": 0.0, "duration": 0.3,
     "audio": "blip", "curve": "spike"},
]
DATA_SCHEMA = {
    "required": ["series"],
    "types": {"title": str, "x_label": str, "y_label": str, "series": list,
              "highlight_points": list},
    "children": {
        "series": {"required": ["label", "points"],
                    "types": {"label": str, "points": list, "emphasized": bool}},
        "highlight_points": {"required": ["series", "at"],
                              "types": {"series": int, "at": list, "label": str}},
    },
}
PARAMS = {}
NEEDS_CONTENT = False
DEPRECATED = False


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    visuals = clip.get("visuals", {})
    data = visuals.get("data") or {}
    series_in = data.get("series") or []
    if not series_in:
        return f"        alive_wait(self, {max(duration, 0.5):.2f}, particles=bg)\n"

    title = data.get("title", "").replace('"', '\\"')
    x_label = data.get("x_label", "").replace('"', '\\"')
    y_label = data.get("y_label", "").replace('"', '\\"')

    all_x = [p[0] for s in series_in for p in s["points"]]
    all_y = [p[1] for s in series_in for p in s["points"]]
    xr = _nice_ticks(min(all_x), max(all_x))
    yr = _nice_ticks(min(all_y + [0]), max(all_y))
    chart_h, chart_w = 4.0, 9.0

    draw_dur = max((duration - 2.5) / max(len(series_in), 1), 0.6)
    lines: list[str] = []
    if title:
        lines.append(
            f'        title = Text("{title}", font="Courier", weight=BOLD).scale(0.5).to_edge(UP, buff=0.5)\n'
            f'        self.play(FadeIn(title), run_time=0.4)\n'
        )
    lines.append(
        f'        ax = Axes(\n'
        f'            x_range=[{xr[0]}, {xr[-1]}, {xr[1] - xr[0]}],\n'
        f'            y_range=[{yr[0]}, {yr[-1]}, {yr[1] - yr[0]}],\n'
        f'            x_length={chart_w}, y_length={chart_h},\n'
        f'            axis_config={{"color": TEXT_DIM, "include_tip": False, "stroke_width": 2}},\n'
        f'        ).to_edge(DOWN, buff=1.0)\n'
        f'        ax.get_x_axis().add_numbers(font_size=18, color=TEXT_DIM)\n'
        f'        ax.get_y_axis().add_numbers(font_size=18, color=TEXT_DIM)\n'
        f'        self.play(Create(ax), run_time=0.7)\n'
    )
    if x_label:
        lines.append(
            f'        xl = Text("{x_label}", font="Courier", color=TEXT_DIM).scale(0.35)\n'
            f'        xl.next_to(ax.get_x_axis(), DOWN, buff=0.3)\n'
            f'        self.play(FadeIn(xl), run_time=0.2)\n'
        )
    if y_label:
        lines.append(
            f'        yl = Text("{y_label}", font="Courier", color=TEXT_DIM).scale(0.35)\n'
            f'        yl.rotate(PI / 2).next_to(ax.get_y_axis(), LEFT, buff=0.3)\n'
            f'        self.play(FadeIn(yl), run_time=0.2)\n'
        )

    for i, s in enumerate(series_in):
        pts = s["points"]
        label = s["label"].replace('"', '\\"')
        emph = bool(s.get("emphasized", False))
        col = "GOLD" if emph else ("GLOW" if i == 0 else "TEXT_DIM")
        points_list = ", ".join(f"ax.c2p({p[0]}, {p[1]})" for p in pts)
        lines.append(
            f'        line_{i} = VMobject(color={col}, stroke_width=3)\n'
            f'        line_{i}.set_points_as_corners([{points_list}])\n'
            f'        self.play(Create(line_{i}), run_time={draw_dur:.2f})\n'
            f'        end_dot_{i} = Dot(ax.c2p({pts[-1][0]}, {pts[-1][1]}), color={col}, radius=0.08)\n'
            f'        end_lbl_{i} = Text("{label}", font="Courier", color={col}).scale(0.35)\n'
            f'        end_lbl_{i}.next_to(end_dot_{i}, RIGHT, buff=0.15)\n'
            f'        self.play(FadeIn(end_dot_{i}), FadeIn(end_lbl_{i}), run_time=0.3)\n'
        )

    for j, h in enumerate(data.get("highlight_points") or []):
        x, y = h["at"]
        lbl = str(h.get("label", "")).replace('"', '\\"')
        lines.append(
            f'        hp_{j} = Dot(ax.c2p({x}, {y}), color=GOLD, radius=0.13)\n'
            f'        hp_lbl_{j} = Text("{lbl}", font="Courier", color=GOLD, weight=BOLD).scale(0.35)\n'
            f'        hp_lbl_{j}.next_to(hp_{j}, UP, buff=0.2)\n'
            f'        self.play(FadeIn(hp_{j}, scale=1.6), FadeIn(hp_lbl_{j}), run_time=0.4)\n'
        )

    hold = max(duration - (0.7 + len(series_in) * (draw_dur + 0.3)) - 1.0, 0.5)
    lines.append(f'        alive_wait(self, {hold:.2f}, particles=bg)\n')
    return "".join(lines)
