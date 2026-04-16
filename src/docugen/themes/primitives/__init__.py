"""Auto-discovering primitive registry.

Every module in this package (except those starting with _) is treated as
a primitive. At import time we validate each module has the required
attributes and cache them by NAME.
"""
from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType

from docugen.themes.primitives._base import REQUIRED_ATTRS

_cache: dict[str, ModuleType] = {}


def _validate_required_attrs(name: str, mod: ModuleType) -> None:
    for attr in REQUIRED_ATTRS:
        if not hasattr(mod, attr):
            raise ImportError(
                f"Primitive {name!r} missing required attr {attr!r}"
            )


def discover_primitives() -> dict[str, ModuleType]:
    """Discover and cache all primitive modules in this package."""
    if _cache:
        return _cache
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_"):
            continue
        mod = importlib.import_module(f"{__name__}.{info.name}")
        _validate_required_attrs(info.name, mod)
        _cache[mod.NAME] = mod
    return dict(_cache)


def get_primitive(name: str) -> ModuleType:
    """Return the primitive module for the given NAME."""
    primitives = discover_primitives()
    if name not in primitives:
        raise KeyError(f"no primitive registered: {name!r}")
    return primitives[name]
