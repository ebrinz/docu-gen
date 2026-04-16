"""title — title + subtitle reveal. Metadata primitive; rendering is delegated
to tools/title.py for standalone title cards. This module exists so the
registry can validate slide_type='title' clips and expose their cue events."""

NAME = "title"
DESCRIPTION = "Title + subtitle with configurable reveal style"
CUE_EVENTS = {"reveal_title", "reveal_subtitle"}
AUDIO_SPANS = [
    {"trigger": "reveal_title", "offset": -2.0, "duration": 2.0,
     "audio": "tension_build", "curve": "ramp_up"},
    {"trigger": "reveal_title", "offset": 0.0, "duration": 0.3,
     "audio": "hit", "curve": "spike"},
    {"trigger": "reveal_subtitle", "offset": 0.0, "duration": 1.2,
     "audio": "sweep_tone", "curve": "linear"},
]
DATA_SCHEMA = {
    "required": [],
    "types": {"title_text": str, "subtitle_text": str, "reveal_style": str},
    "enums": {"reveal_style": {"particle", "glitch", "trace", "typewriter"}},
}
PARAMS = {"reveal_style": "particle"}
NEEDS_CONTENT = False
DEPRECATED = False


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    visuals = clip.get("visuals", {})
    params = visuals.get("params", {}) or {}
    style = params.get("reveal_style", "particle")
    title_text = (params.get("title_text") or clip.get("text", "")).replace('"', '\\"')
    subtitle = (params.get("subtitle_text") or "").replace('"', '\\"')
    hold = max(duration - 4.0, 1.0)
    return (
        f'        title = Text("{title_text}", font="Courier", weight=BOLD).scale(1.0)\n'
        f'        subtitle = Text("{subtitle}", font="Courier").scale(0.5)\n'
        f'        subtitle.next_to(title, DOWN, buff=0.5)\n'
        f'        self.play(FadeIn(title, shift=UP * 0.3), run_time=1.5)\n'
        f'        self.play(FadeIn(subtitle, shift=UP * 0.2), run_time=1.0)\n'
        f'        self.wait({hold:.2f})\n'
        f'        self.play(FadeOut(title), FadeOut(subtitle), run_time=1.0)\n'
        f'        # reveal_style={style!r}\n'
    )
