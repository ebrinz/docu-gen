"""Auto-discovery registry tests."""
import pytest
from docugen.themes.primitives import discover_primitives, get_primitive


def test_discover_returns_dict():
    result = discover_primitives()
    assert isinstance(result, dict)


def test_get_unknown_primitive_raises():
    with pytest.raises(KeyError, match="no_such_primitive"):
        get_primitive("no_such_primitive")


def test_missing_required_attr_raises(tmp_path, monkeypatch):
    """A module in the primitives package missing a REQUIRED_ATTR must fail
    import-time validation with an ImportError naming the module and attr."""
    import importlib
    import sys
    import docugen.themes.primitives as pkg

    # Reset cache so this test is independent of prior discovery.
    pkg._cache.clear()

    # Drop a malformed primitive next to the package on a temp path.
    malformed = tmp_path / "broken.py"
    malformed.write_text(
        "NAME = 'broken'\n"
        "DESCRIPTION = 'missing render + schema'\n"
        "CUE_EVENTS = set()\n"
        "AUDIO_SPANS = []\n"
        # intentionally missing DATA_SCHEMA and render
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    # Temporarily extend the package path so discover picks up our fake module.
    monkeypatch.setattr(pkg, "__path__", list(pkg.__path__) + [str(tmp_path)])

    with pytest.raises(ImportError, match="broken"):
        pkg.discover_primitives()

    # Leave the cache clean for subsequent tests.
    pkg._cache.clear()
