"""Shared Protocol + helpers for primitive modules."""
from __future__ import annotations

from typing import Protocol


class PrimitiveModule(Protocol):
    NAME: str
    DESCRIPTION: str
    CUE_EVENTS: set[str]
    AUDIO_SPANS: list[dict]
    DATA_SCHEMA: dict
    NEEDS_CONTENT: bool
    DEPRECATED: bool
    PARAMS: dict

    def render(self, clip: dict, duration: float,
               images_dir: str, theme) -> str: ...


REQUIRED_ATTRS = ("NAME", "DESCRIPTION", "CUE_EVENTS", "AUDIO_SPANS",
                  "DATA_SCHEMA", "render")
