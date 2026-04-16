"""Auto-discovery registry tests."""
import pytest
from docugen.themes.primitives import discover_primitives, get_primitive


def test_discover_returns_dict():
    result = discover_primitives()
    assert isinstance(result, dict)


def test_get_unknown_primitive_raises():
    with pytest.raises(KeyError, match="no_such_primitive"):
        get_primitive("no_such_primitive")
