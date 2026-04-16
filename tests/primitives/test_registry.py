"""Auto-discovery registry tests."""
import pytest
from docugen.themes.primitives import discover_primitives, get_primitive


def test_discover_returns_dict():
    result = discover_primitives()
    assert isinstance(result, dict)


def test_get_unknown_primitive_raises():
    with pytest.raises(KeyError, match="no_such_primitive"):
        get_primitive("no_such_primitive")


def test_validate_required_attrs_raises_on_missing():
    """_validate_required_attrs raises ImportError naming the module and
    missing attribute. This is the pure validation contract that underpins
    discover_primitives' fail-loud behavior."""
    from types import ModuleType
    from docugen.themes.primitives import _validate_required_attrs

    mod = ModuleType("bad_prim")
    mod.NAME = "bad_prim"
    # NAME is set but DESCRIPTION, CUE_EVENTS, AUDIO_SPANS, DATA_SCHEMA, render are not
    with pytest.raises(ImportError, match="bad_prim"):
        _validate_required_attrs("bad_prim", mod)


def test_validate_required_attrs_passes_when_complete():
    """When every REQUIRED_ATTR is present, validation does not raise."""
    from types import ModuleType
    from docugen.themes.primitives import _validate_required_attrs

    mod = ModuleType("ok_prim")
    mod.NAME = "ok_prim"
    mod.DESCRIPTION = "d"
    mod.CUE_EVENTS = set()
    mod.AUDIO_SPANS = []
    mod.DATA_SCHEMA = {}
    mod.render = lambda clip, duration, images_dir, theme: ""

    _validate_required_attrs("ok_prim", mod)  # must not raise
