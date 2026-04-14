# tests/test_compose.py
import pytest
from docugen.renderers import register_renderer, get_renderer, RENDERERS


def test_register_and_retrieve_renderer():
    def dummy(node, inputs, clip, project_path):
        return project_path / "out.mp4"

    register_renderer("test_dummy", dummy)
    assert get_renderer("test_dummy") is dummy


def test_get_unknown_renderer_raises():
    with pytest.raises(KeyError, match="no_such_renderer"):
        get_renderer("no_such_renderer")


def test_registry_rejects_non_callable():
    with pytest.raises(TypeError):
        register_renderer("bad", "not_a_function")
