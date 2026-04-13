"""Abstract base class for docu-gen visual themes."""

from abc import ABC, abstractmethod


class ThemeBase(ABC):
    name: str
    palette: dict[str, str]
    font: str

    @abstractmethod
    def manim_header(self) -> str:
        """Return Manim preamble: imports, palette, helper functions."""

    @abstractmethod
    def render_theme_layer(self, elements: list[str]) -> str:
        """Return Manim code that sets up background elements.

        Returns indented code lines ready for a construct() body.
        """

    @abstractmethod
    def render_content_layer(self, assets: list[str], placement: str,
                             images_dir: str) -> str:
        """Return Manim code that places content assets.

        Returns indented code lines. Empty string if no assets.
        """

    @abstractmethod
    def render_choreography(self, choreo_type: str, params: dict,
                            duration: float, images_dir: str) -> str:
        """Return Manim code for animation choreography.

        Returns indented code lines. Empty string if no choreography.
        """

    def build_scene(self, clip: dict, duration: float, images_dir: str,
                    chapter_num: str = "00", chapter_title: str = "") -> str:
        """Build complete Manim script for a clip using three layers.

        Composes: header + theme layer + content layer + choreography + ambient hold.
        """
        clip_id = clip["clip_id"]
        visuals = clip.get("visuals", {})

        # Layer 1: Theme elements
        elements = visuals.get("theme_elements",
                               ["hex_grid", "imperial_border", "floating_bg"])
        theme_code = self.render_theme_layer(elements)

        # Layer 2: Content
        content = visuals.get("content", {})
        assets = content.get("assets", visuals.get("assets", []))
        placement = content.get("placement", "center")
        content_code = self.render_content_layer(assets, placement, images_dir)

        # Layer 3: Choreography
        choreo = visuals.get("choreography", {})
        choreo_type = choreo.get("type", visuals.get("type", ""))
        choreo_params = choreo.get("params", {})

        # Handle legacy chapter_card type
        if choreo_type == "chapter_card":
            choreo_params.setdefault("num", chapter_num)
            choreo_params.setdefault("title", chapter_title)

        choreo_code = self.render_choreography(
            choreo_type, choreo_params, duration, images_dir)

        # Compose
        hold_time = max(duration * 0.15, 0.5)
        has_bg = "floating_bg" in elements

        script = self.manim_header() + f'''

class Scene_{clip_id}(Scene):
    def construct(self):
{theme_code}
{content_code}
{choreo_code}
        {"alive_wait(self, " + f"{hold_time:.1f}, particles=bg)" if has_bg else f"self.wait({hold_time:.1f})"}
'''
        return script

    # Legacy interface — default implementations call build_scene
    def idle_scene(self, duration: float) -> str:
        clip = {"clip_id": "idle", "visuals": {
            "theme_elements": ["hex_grid", "imperial_border", "floating_bg"],
        }}
        return self.build_scene(clip, duration, "")

    def chapter_card(self, num: str, title: str, duration: float) -> str:
        clip = {"clip_id": "chapter_card", "visuals": {
            "theme_elements": ["hex_grid", "imperial_border", "floating_bg"],
            "choreography": {"type": "chapter_card", "params": {"num": num, "title": title}},
        }}
        return self.build_scene(clip, duration, "")

    def image_reveal(self, assets: list[str], direction: str,
                     duration: float, images_dir: str) -> str:
        clip = {"clip_id": "image_reveal", "visuals": {
            "theme_elements": ["hex_grid", "imperial_border", "floating_bg"],
            "content": {"assets": assets, "placement": "center"},
        }}
        return self.build_scene(clip, duration, images_dir)

    def data_reveal(self, direction: str, duration: float) -> str:
        clip = {"clip_id": "data_reveal", "visuals": {
            "theme_elements": ["hex_grid", "imperial_border", "floating_bg"],
            "choreography": {"type": "data_text", "params": {"text": direction}},
        }}
        return self.build_scene(clip, duration, "")

    def custom_animation(self, direction: str, duration: float,
                         assets: list[str], images_dir: str) -> str:
        clip = {"clip_id": "custom_animation", "visuals": {
            "theme_elements": ["hex_grid", "imperial_border", "floating_bg"],
            "content": {"assets": assets, "placement": "center"},
        }}
        return self.build_scene(clip, duration, images_dir)

    @abstractmethod
    def transition_sounds(self) -> dict[str, callable]:
        """Return dict mapping sound names to audio generator functions."""

    @abstractmethod
    def chapter_layers(self) -> dict[str, callable]:
        """Return dict mapping layer names to drone layer generator functions."""
