"""ambient_field — theme background holds for the clip duration."""

NAME = "ambient_field"
DESCRIPTION = "Particle field + theme bg, no foreground content"
CUE_EVENTS: set[str] = set()
AUDIO_SPANS: list[dict] = []
DATA_SCHEMA = {"required": [], "types": {}}
PARAMS = {}
NEEDS_CONTENT = False
DEPRECATED = False


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    # Ambient field — breathing pause
    return (
        f"        line = Line(LEFT * 2, RIGHT * 2, color=GOLD, stroke_width=1, stroke_opacity=0.3)\n"
        f"        self.add(line)\n"
        f"        alive_wait(self, {duration:.1f}, particles=bg)\n"
    )
