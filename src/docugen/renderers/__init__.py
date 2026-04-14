"""Renderer plugin registry — auto-discovers and registers render node handlers."""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Callable, Protocol

from pathlib import Path as PathType


class RendererFn(Protocol):
    def __call__(
        self,
        node: dict,
        inputs: dict[str, PathType],
        clip: dict,
        project_path: PathType,
    ) -> PathType: ...


RENDERERS: dict[str, RendererFn] = {}


def register_renderer(name: str, fn: RendererFn) -> None:
    if not callable(fn):
        raise TypeError(f"Renderer must be callable, got {type(fn)}")
    RENDERERS[name] = fn


def get_renderer(name: str) -> RendererFn:
    if name not in RENDERERS:
        raise KeyError(f"Unknown renderer '{name}' — registered: {list(RENDERERS)}")
    return RENDERERS[name]


def discover_renderers() -> None:
    """Import all modules in this package to trigger registration."""
    pkg_dir = Path(__file__).parent
    for info in pkgutil.iter_modules([str(pkg_dir)]):
        if info.name.startswith("_"):
            continue
        importlib.import_module(f"docugen.renderers.{info.name}")
