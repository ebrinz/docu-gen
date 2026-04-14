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


from pathlib import Path
from docugen.compose import topo_sort, content_hash, render_clip_dag


def test_topo_sort_linear():
    nodes = [
        {"name": "bg", "renderer": "manim_theme"},
        {"name": "choreo", "renderer": "manim_choreo", "refs": ["bg"]},
        {"name": "composite", "renderer": "ffmpeg_composite", "inputs": ["bg", "choreo"]},
    ]
    order = topo_sort(nodes)
    names = [n["name"] for n in order]
    assert names.index("bg") < names.index("choreo")
    assert names.index("choreo") < names.index("composite")


def test_topo_sort_detects_cycle():
    nodes = [
        {"name": "a", "renderer": "x", "refs": ["b"]},
        {"name": "b", "renderer": "x", "refs": ["a"]},
    ]
    with pytest.raises(ValueError, match="cycle"):
        topo_sort(nodes)


def test_content_hash_stable():
    node = {"name": "bg", "renderer": "manim_theme", "elements": ["hex_grid"]}
    clip = {"clip_id": "intro_01", "text": "hello"}
    h1 = content_hash(node, clip, input_hashes={})
    h2 = content_hash(node, clip, input_hashes={})
    assert h1 == h2


def test_content_hash_changes_on_node_change():
    clip = {"clip_id": "intro_01", "text": "hello"}
    h1 = content_hash({"name": "bg", "renderer": "manim_theme", "elements": ["hex_grid"]},
                       clip, input_hashes={})
    h2 = content_hash({"name": "bg", "renderer": "manim_theme", "elements": ["hex_grid", "particles"]},
                       clip, input_hashes={})
    assert h1 != h2
