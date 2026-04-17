import ast
from docugen.themes.primitives import llm_custom
from docugen.themes.primitives._base import validate_schema


def test_metadata():
    assert llm_custom.NAME == "llm_custom"
    assert llm_custom.CUE_EVENTS == set()


def test_schema_requires_script_and_rationale():
    errs = validate_schema({}, llm_custom.DATA_SCHEMA, "data")
    assert any("custom_script" in e for e in errs)
    assert any("rationale" in e for e in errs)


def test_render_returns_placeholder():
    clip = {"clip_id": "x", "text": "",
            "visuals": {"slide_type": "llm_custom",
                        "data": {"custom_script": "class S: ...",
                                 "rationale": "X"}}}
    body = llm_custom.render(clip, duration=4.0, images_dir="/tmp", theme=None)
    ast.parse("def construct(self):\n" + body)
