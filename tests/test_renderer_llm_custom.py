import ast
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

from docugen.renderers.manim_llm_custom import (
    ast_check_script, render_node,
)


VALID_SCRIPT = '''from manim import *

class Scene_x(Scene):
    def construct(self):
        self.wait(1)
'''

BROKEN_SCRIPT = 'from manim import * \n class Scene_x Scene):'  # SyntaxError


def test_ast_check_accepts_valid():
    assert ast_check_script(VALID_SCRIPT) is None


def test_ast_check_rejects_broken():
    err = ast_check_script(BROKEN_SCRIPT)
    assert err is not None
    assert "SyntaxError" in err or "invalid syntax" in err


@patch("docugen.renderers.manim_llm_custom.load_config")
@patch("docugen.renderers.manim_llm_custom.subprocess.run")
def test_render_node_writes_script_and_invokes_manim(mock_run, mock_cfg, tmp_path):
    mock_cfg.return_value = {"video": {"fps": 60}}

    clip = {
        "clip_id": "test_01",
        "visuals": {"slide_type": "llm_custom",
                    "data": {"custom_script": VALID_SCRIPT,
                             "rationale": "no primitive fits"}},
        "timing": {"clip_duration": 4.0},
    }

    # Mocked manim creates its output file as a side effect of being "run".
    def fake_manim(cmd, capture_output=True, text=True):
        media_dir = Path(tmp_path) / "build" / "clips" / "test_01" / "media"
        out_dir = media_dir / "videos" / "_scene" / "480p15"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "Scene_test_01.mp4").write_bytes(b"fakevideo")
        return MagicMock(returncode=0, stderr="")

    mock_run.side_effect = fake_manim

    node = {"name": "llm_custom", "renderer": "manim_llm_custom"}
    out = render_node(node, {}, clip, tmp_path, theme=None)
    assert Path(out).exists()
    assert mock_run.called


def test_render_node_raises_on_bad_script(tmp_path):
    clip = {
        "clip_id": "bad",
        "visuals": {"slide_type": "llm_custom",
                    "data": {"custom_script": BROKEN_SCRIPT,
                             "rationale": "testing"}},
    }
    node = {"name": "llm_custom", "renderer": "manim_llm_custom"}
    with pytest.raises(RuntimeError, match="AST check"):
        render_node(node, {}, clip, tmp_path, theme=None)
