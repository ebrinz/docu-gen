"""default_dag routes llm_custom clips to the manim_llm_custom renderer."""
from docugen.themes import load_theme


def test_default_dag_uses_llm_custom_renderer_for_llm_custom_clip():
    theme = load_theme("biopunk")
    clip = {
        "clip_id": "x",
        "visuals": {"slide_type": "llm_custom",
                    "data": {"custom_script": "class S: pass",
                             "rationale": "R"}},
    }
    nodes = theme.default_dag(clip)
    renderers = {n["renderer"] for n in nodes}
    assert "manim_llm_custom" in renderers
    # The fused-scene manim_choreo path should NOT be present for llm_custom
    assert "manim_choreo" not in renderers


def test_default_dag_keeps_fused_path_for_typed_primitives():
    theme = load_theme("biopunk")
    clip = {
        "clip_id": "y",
        "visuals": {"slide_type": "callout",
                    "data": {"primary": "$41"}},
    }
    nodes = theme.default_dag(clip)
    renderers = {n["renderer"] for n in nodes}
    assert "manim_choreo" in renderers
    assert "manim_llm_custom" not in renderers
