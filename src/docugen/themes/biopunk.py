"""Biopunk visual theme stub — full implementation in Task 2."""

from docugen.themes.base import ThemeBase

palette = {
    "bg": "#050510", "panel": "#0a0e1a", "glow": "#b8ffc4", "glow_dim": "#4a7a52",
    "purple": "#8b5cf6", "purple_deep": "#5b21b6", "purple_faint": "#3b1a6e",
    "sith_red": "#dc2626", "sith_red_dim": "#7f1d1d", "cyan": "#22d3ee",
    "gold": "#f59e0b", "text": "#e2e8f0", "text_dim": "#64748b", "grid": "#1a1a2e",
}
font = "Courier"


class BiopunkTheme(ThemeBase):
    name = "biopunk"
    palette = palette
    font = font

    def manim_header(self) -> str:
        return ""

    def idle_scene(self, duration: float) -> str:
        return ""

    def chapter_card(self, num: str, title: str, duration: float) -> str:
        return ""

    def image_reveal(self, assets: list[str], direction: str,
                     duration: float, images_dir: str) -> str:
        return ""

    def data_reveal(self, direction: str, duration: float) -> str:
        return ""

    def custom_animation(self, direction: str, duration: float,
                         assets: list[str], images_dir: str) -> str:
        return ""

    def transition_sounds(self) -> dict[str, callable]:
        return {}

    def chapter_layers(self) -> dict[str, callable]:
        return {}


theme = BiopunkTheme()
