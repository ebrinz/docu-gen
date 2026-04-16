"""Auto-discovering primitive registry.

Every module in this package (except those starting with _) is treated as
a primitive. At import time we validate each module has the required
attributes and cache them by NAME.
"""
from __future__ import annotations

import importlib
import importlib.util
import pkgutil
from pathlib import Path
from types import ModuleType

from docugen.themes.primitives._base import REQUIRED_ATTRS

_cache: dict[str, ModuleType] = {}


def _load_module(name: str, finder: pkgutil.ImpImporter | object) -> ModuleType:
    """Load a primitive module by name, using its finder for the file location."""
    # Try the normal dotted-name import first (real sub-modules).
    full_name = f"{__name__}.{name}"
    spec = importlib.util.find_spec(full_name)
    if spec is not None and spec.origin is not None:
        return importlib.import_module(full_name)
    # Fall back: locate via the finder (handles injected tmp_path entries).
    file_finder = getattr(finder, "path", None)
    if file_finder is not None:
        candidate = Path(file_finder) / f"{name}.py"
        if candidate.exists():
            spec = importlib.util.spec_from_file_location(name, candidate)
            if spec is not None and spec.loader is not None:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)  # type: ignore[union-attr]
                return mod
    raise ImportError(f"Cannot locate primitive module {name!r}")


def discover_primitives() -> dict[str, ModuleType]:
    """Discover and cache all primitive modules in this package."""
    if _cache:
        return _cache
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_"):
            continue
        mod = _load_module(info.name, info.module_finder)
        for attr in REQUIRED_ATTRS:
            if not hasattr(mod, attr):
                raise ImportError(
                    f"Primitive {info.name!r} missing required attr {attr!r}"
                )
        _cache[mod.NAME] = mod
    return dict(_cache)


def get_primitive(name: str) -> ModuleType:
    """Return the primitive module for the given NAME."""
    primitives = discover_primitives()
    if name not in primitives:
        raise KeyError(f"no primitive registered: {name!r}")
    return primitives[name]
