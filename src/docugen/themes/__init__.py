"""Theme registry — discover and load visual themes."""

import importlib
import pkgutil
from pathlib import Path

from docugen.themes.base import ThemeBase


def list_themes() -> list[str]:
    """List available theme names by scanning the themes package."""
    themes_dir = Path(__file__).parent
    names = []
    for info in pkgutil.iter_modules([str(themes_dir)]):
        if info.name not in ("base", "__init__"):
            names.append(info.name)
    return sorted(names)


def load_theme(name: str) -> ThemeBase:
    """Load a theme module by name and return its theme instance."""
    available = list_themes()
    if name not in available:
        raise ValueError(f"Unknown theme '{name}'. Available: {available}")
    module = importlib.import_module(f"docugen.themes.{name}")
    return module.theme
