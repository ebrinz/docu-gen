"""svg_reveal — SVG asset fades/draws in with labels."""

NAME = "svg_reveal"
DESCRIPTION = "SVG asset fades/draws in, Ken Burns drift, labels"
CUE_EVENTS = {"show_asset", "highlight_region", "show_label"}
AUDIO_SPANS = [
    {"trigger": "show_asset", "offset": 0.0, "duration": 1.0,
     "audio": "swoosh", "curve": "ease_in"},
    {"trigger": "show_label", "offset": 0.0, "duration": 0.3,
     "audio": "blip", "curve": "spike"},
]
DATA_SCHEMA = {"required": [], "types": {}}
PARAMS = {}
NEEDS_CONTENT = True
DEPRECATED = False


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    # SVG reveal — content layer handles asset, choreo holds
    hold = max(duration - 2.0, 1.0)
    return f"        alive_wait(self, {hold:.1f}, particles=bg)\n"
