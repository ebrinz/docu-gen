"""callout — primary/secondary typographic callout. Rename of legacy data_text."""

NAME = "callout"
DESCRIPTION = "Headline number + annotation, clean typography"
CUE_EVENTS = {"show_primary", "show_secondary"}
AUDIO_SPANS = [
    {"trigger": "show_primary", "offset": 0.0, "duration": 0.3,
     "audio": "blip", "curve": "spike"},
    {"trigger": "show_secondary", "offset": 0.0, "duration": 0.3,
     "audio": "blip", "curve": "spike"},
]
DATA_SCHEMA = {
    "required": ["primary"],
    "types": {"primary": str, "secondary": str, "style": str},
    "enums": {"style": {"headline", "tag", "label"}},
}
PARAMS = {}
NEEDS_CONTENT = False
DEPRECATED = False


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    visuals = clip.get("visuals", {})
    data = visuals.get("data") or {}
    primary = str(data.get("primary", "")).replace('"', '\\"')
    secondary = str(data.get("secondary", "")).replace('"', '\\"')
    style = data.get("style", "headline")
    scale_map = {"headline": 1.6, "tag": 0.8, "label": 0.55}
    scale = scale_map.get(style, 1.6)
    hold = max(duration - 2.0, 0.5)
    lines = [
        f'        primary = Text("{primary}", font="Courier", weight=BOLD).scale({scale})\n',
        f'        self.play(FadeIn(primary, scale=1.15), run_time=0.6)\n',
    ]
    if secondary:
        lines.append(
            f'        secondary = Text("{secondary}", font="Courier", color=TEXT_DIM).scale(0.45)\n'
            f'        secondary.next_to(primary, DOWN, buff=0.4)\n'
            f'        self.play(FadeIn(secondary), run_time=0.4)\n'
        )
    lines.append(f'        alive_wait(self, {hold:.2f}, particles=bg)\n')
    return "".join(lines)
