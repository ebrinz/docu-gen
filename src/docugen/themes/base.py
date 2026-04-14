"""Abstract base class for docu-gen visual themes."""

from abc import ABC, abstractmethod
from pathlib import Path


class ThemeBase(ABC):
    name: str
    palette: dict[str, str]

    @abstractmethod
    def manim_header(self) -> str:
        """Return Manim preamble: imports, palette constants, helper functions."""

    def default_dag(self, clip: dict) -> list[dict]:
        """Return the default DAG node list for a clip.

        Theme decides what layers a clip needs based on
        slide_type, assets, cue_words, etc. Can vary per clip.
        """
        raise NotImplementedError(f"{self.name} theme must implement default_dag()")

    @abstractmethod
    def render_theme_layer(self, elements: list[str]) -> str:
        """Return Manim code that sets up background elements.

        Returns indented code lines ready for a construct() body.
        Used by the fused manim renderer to compose scenes.
        """

    @abstractmethod
    def render_content_layer(self, assets: list[str], placement: str,
                             images_dir: str) -> str:
        """Return Manim code that places content assets.

        Returns indented code lines. Empty string if no assets.
        Used by the fused manim renderer to compose scenes.
        """

    @abstractmethod
    def render_choreography(self, clip: dict, duration: float,
                            images_dir: str) -> str:
        """Return Manim code for animation choreography.

        Receives the full clip dict including word_times and
        visuals.cue_words for word-level sync. When fused,
        can reference self.layers for cross-layer mobject access.

        Returns indented code lines.
        """

    @abstractmethod
    def transition_sounds(self) -> dict[str, callable]:
        """Return dict mapping sound names to audio generator functions."""

    @abstractmethod
    def chapter_layers(self) -> dict[str, callable]:
        """Return dict mapping layer names to drone layer generator functions."""
