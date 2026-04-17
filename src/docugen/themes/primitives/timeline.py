"""timeline — events on an axis (horizontal default)."""

import re

NAME = "timeline"
DESCRIPTION = "Events on a horizontal (or vertical) axis, ordered temporally"
CUE_EVENTS = {"draw_axis", "reveal_event", "highlight_event"}
AUDIO_SPANS = [
    {"trigger": "draw_axis", "offset": 0.0, "duration": 0.5,
     "audio": "swoosh", "curve": "ease_in"},
    {"trigger": "reveal_event", "offset": 0.0, "duration": 0.4,
     "audio": "tick", "curve": "ease_in"},
    {"trigger": "highlight_event", "offset": 0.0, "duration": 0.3,
     "audio": "blip", "curve": "spike"},
]
DATA_SCHEMA = {
    "required": ["range", "events"],
    "types": {"range": dict, "events": list, "orientation": str},
    "enums": {"orientation": {"horizontal", "vertical"}},
    "children": {
        "range": {"required": ["start", "end"],
                   "types": {"start": str, "end": str}},
        "events": {"required": ["at", "label"],
                    "types": {"at": str, "label": str, "marker": str,
                              "emphasized": bool}},
    },
}
PARAMS = {}
NEEDS_CONTENT = False
DEPRECATED = False


def _parse_at(s: str) -> float:
    """Parse a date-ish string to a fractional year."""
    s = s.strip()
    m = re.match(r"^(\d{4})(?:-(Q[1-4]|\d{1,2}))?", s)
    if not m:
        return 0.0
    year = int(m.group(1))
    suf = m.group(2)
    if not suf:
        return float(year)
    if suf.startswith("Q"):
        return year + (int(suf[1]) - 1) * 0.25
    return year + (int(suf) - 1) / 12.0


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    visuals = clip.get("visuals", {})
    data = visuals.get("data") or {}
    rng = data.get("range") or {}
    events = data.get("events") or []
    if not events:
        return f"        alive_wait(self, {max(duration, 0.5):.2f}, particles=bg)\n"

    orientation = data.get("orientation", "horizontal")
    t_start = _parse_at(rng.get("start", ""))
    t_end = _parse_at(rng.get("end", ""))
    if t_end <= t_start:
        t_end = t_start + 1.0

    axis_len = 10.0

    def pos(t):
        frac = (t - t_start) / (t_end - t_start)
        u = -axis_len / 2 + frac * axis_len
        return (u, 0.0) if orientation == "horizontal" else (0.0, u)

    lines: list[str] = []
    if orientation == "horizontal":
        lines.append(
            f'        axis = Line(LEFT * {axis_len/2}, RIGHT * {axis_len/2},\n'
            f'                    color=TEXT_DIM, stroke_width=2)\n'
            f'        self.play(Create(axis), run_time=0.6)\n'
        )
    else:
        lines.append(
            f'        axis = Line(UP * {axis_len/2}, DOWN * {axis_len/2},\n'
            f'                    color=TEXT_DIM, stroke_width=2)\n'
            f'        self.play(Create(axis), run_time=0.6)\n'
        )

    ordered = sorted(events, key=lambda e: _parse_at(e["at"]))
    reveal_dur = max((duration - 2.0) / max(len(ordered), 1), 0.3)
    for i, ev in enumerate(ordered):
        x, y = pos(_parse_at(ev["at"]))
        label = ev["label"].replace('"', '\\"')
        at_str = ev["at"].replace('"', '\\"')
        marker = ev.get("marker", "dot")
        emph = bool(ev.get("emphasized", False))
        col = "GOLD" if emph else "GLOW"
        radius = 0.14 if emph else 0.08
        if marker == "star":
            marker_ctor = f'Star([{x:.3f}, {y:.3f}, 0], color={col}, outer_radius={radius + 0.05})'
        else:
            marker_ctor = f'Dot([{x:.3f}, {y:.3f}, 0], color={col}, radius={radius})'

        off = (0.0, 0.8) if orientation == "horizontal" else (1.2, 0.0)
        if orientation == "horizontal" and i % 2 == 1:
            off = (0.0, -0.8)

        lines.append(
            f'        ev_{i} = {marker_ctor}\n'
            f'        lbl_{i} = VGroup(\n'
            f'            Text("{at_str}", font="Courier", color=TEXT_DIM).scale(0.25),\n'
            f'            Text("{label}", font="Courier", color={col}, weight=BOLD).scale(0.32),\n'
            f'        ).arrange(DOWN, buff=0.08)\n'
            f'        lbl_{i}.move_to([{x + off[0]:.3f}, {y + off[1]:.3f}, 0])\n'
            f'        conn_{i} = Line([{x:.3f}, {y:.3f}, 0],\n'
            f'                        lbl_{i}.get_center(), color=TEXT_DIM, stroke_width=1)\n'
            f'        self.play(FadeIn(ev_{i}, scale=1.5),\n'
            f'                  Create(conn_{i}), FadeIn(lbl_{i}),\n'
            f'                  run_time={reveal_dur:.2f})\n'
        )

    hold = max(duration - 0.6 - len(ordered) * reveal_dur - 1.0, 0.5)
    lines.append(f'        alive_wait(self, {hold:.2f}, particles=bg)\n')
    return "".join(lines)
