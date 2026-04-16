"""Auto-discovering primitive registry.

Every module in this package (except those starting with _) is treated as
a primitive. At import time we validate each module has the required
attributes and cache them by NAME.
"""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from types import ModuleType

from docugen.themes.primitives._base import REQUIRED_ATTRS

_cache: dict[str, ModuleType] = {}


def discover_primitives() -> dict[str, ModuleType]:
    """Discover and cache all primitive modules in this package."""
    if _cache:
        return _cache
    pkg_path = Path(__file__).parent
    for info in pkgutil.iter_modules([str(pkg_path)]):
        if info.name.startswith("_"):
            continue
        mod = importlib.import_module(f"{__name__}.{info.name}")
        for attr in REQUIRED_ATTRS:
            if not hasattr(mod, attr):
                raise ImportError(
                    f"Primitive {info.name!r} missing required attr {attr!r}"
                )
        _cache[mod.NAME] = mod
    return _cache


def get_primitive(name: str) -> ModuleType:
    """Return the primitive module for the given NAME."""
    primitives = discover_primitives()
    if name not in primitives:
        raise KeyError(f"no primitive registered: {name!r}")
    return primitives[name]
