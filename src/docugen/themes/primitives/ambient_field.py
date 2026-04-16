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
    hold = max(duration, 0.5)
    return f"        alive_wait(self, {hold:.2f}, particles=bg)\n"
