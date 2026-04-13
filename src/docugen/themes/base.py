"""Abstract base class for docu-gen visual themes."""

from abc import ABC, abstractmethod


class ThemeBase(ABC):
    name: str
    palette: dict[str, str]
    font: str

    @abstractmethod
    def manim_header(self) -> str:
        """Return Manim preamble code: imports, palette constants, helper functions."""

    @abstractmethod
    def idle_scene(self, duration: float) -> str:
        """Return Manim script for a blank themed slide with ambient motion."""

    @abstractmethod
    def chapter_card(self, num: str, title: str, duration: float) -> str:
        """Return Manim script for a chapter title card."""

    @abstractmethod
    def image_reveal(self, assets: list[str], direction: str,
                     duration: float, images_dir: str) -> str:
        """Return Manim script for image/SVG reveal with Ken Burns."""

    @abstractmethod
    def data_reveal(self, direction: str, duration: float) -> str:
        """Return Manim script for text/data appearing on screen."""

    @abstractmethod
    def custom_animation(self, direction: str, duration: float,
                         assets: list[str], images_dir: str) -> str:
        """Return Manim script for a custom animation sequence."""

    @abstractmethod
    def transition_sounds(self) -> dict[str, callable]:
        """Return dict mapping sound names to audio generator functions."""

    @abstractmethod
    def chapter_layers(self) -> dict[str, callable]:
        """Return dict mapping layer names to drone layer generator functions."""

    # -- Animation primitives (default implementations return idle scene) --

    def anim_counter(self, duration, images_dir="", **kw) -> str:
        return self.idle_scene(duration)

    def anim_fingerprint_compare(self, duration, images_dir="", **kw) -> str:
        return self.idle_scene(duration)

    def anim_sonar_ring(self, duration, images_dir="", **kw) -> str:
        return self.idle_scene(duration)

    def anim_anchor_drop(self, duration, images_dir="", **kw) -> str:
        return self.idle_scene(duration)

    def anim_dot_field(self, duration, images_dir="", **kw) -> str:
        return self.idle_scene(duration)

    def anim_remove_reveal(self, duration, images_dir="", **kw) -> str:
        return self.idle_scene(duration)

    def anim_dot_merge(self, duration, images_dir="", **kw) -> str:
        return self.idle_scene(duration)

    def anim_bar_chart(self, duration, images_dir="", **kw) -> str:
        return self.idle_scene(duration)

    def anim_before_after(self, duration, images_dir="", **kw) -> str:
        return self.idle_scene(duration)

    def anim_organism_reveal(self, duration, images_dir="", **kw) -> str:
        return self.idle_scene(duration)
