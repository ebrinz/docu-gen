import ast
from docugen.themes.primitives import tree
from docugen.themes.primitives._base import validate_schema


def test_metadata():
    assert tree.NAME == "tree"
    assert "reveal_root" in tree.CUE_EVENTS


def test_schema_valid():
    data = {"root": {"label": "R", "children": [{"label": "A"}, {"label": "B"}]},
            "layout": "horizontal", "node_style": "box"}
    assert validate_schema(data, tree.DATA_SCHEMA, "data") == []


def test_layout_positions_horizontal():
    root = {"label": "R", "children": [
        {"label": "A", "children": [{"label": "A1"}, {"label": "A2"}]},
        {"label": "B"},
    ]}
    positions = tree._layout(root, layout="horizontal")

    def count(n):
        return 1 + sum(count(c) for c in n.get("children") or [])

    # every node got a position
    assert len(positions) == count(root)
    # root should be at the leftmost depth
    xs = [pos[0] for pos in positions.values()]
    assert positions[id(root)][0] == min(xs)


def test_render_compiles():
    clip = {"clip_id": "x", "text": "",
            "word_times": [{"word": "x", "start": 0.0, "end": 0.3}],
            "visuals": {"slide_type": "tree",
                        "data": {"root": {"label": "R",
                                          "children": [{"label": "A"},
                                                       {"label": "B"}]}},
                        "cue_words": [{"event": "reveal_root", "at_index": 0,
                                       "params": {}}]}}
    body = tree.render(clip, duration=8.0, images_dir="/tmp", theme=None)
    ast.parse("def construct(self):\n" + body)


def test_render_no_root_alive_waits():
    clip = {"clip_id": "x", "visuals": {"slide_type": "tree", "data": {}}}
    body = tree.render(clip, duration=3.0, images_dir="/tmp", theme=None)
    assert "alive_wait" in body
