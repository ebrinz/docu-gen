"""manim_llm_custom — render a raw Manim script from llm_custom clips.

Writes the script, runs manim, and on failure surfaces the traceback so a
higher-level loop (the MCP client re-invocation) can rewrite and retry.
This renderer participates in the DAG's content-hash cache via the script
body, so script edits invalidate the cached output.
"""

from __future__ import annotations

import ast as _ast
import subprocess
from pathlib import Path

from docugen.config import load_config
from docugen.renderers import register_renderer


def ast_check_script(script: str) -> str | None:
    """Return None if the script is syntactically valid, else an error string."""
    try:
        _ast.parse(script)
    except SyntaxError as e:
        return f"SyntaxError at line {e.lineno}: {e.msg}"
    return None


def render_node(node, inputs, clip, project_path, theme=None):
    project_path = Path(project_path)
    clip_id = clip["clip_id"]

    visuals = clip.get("visuals", {})
    data = visuals.get("data") or {}
    script = data.get("custom_script", "")

    # Fail fast on invalid script before touching config / filesystem.
    err = ast_check_script(script)
    if err:
        raise RuntimeError(
            f"llm_custom script for {clip_id} failed AST check: {err}"
        )

    config = load_config(project_path)
    clip_dir = project_path / "build" / "clips" / clip_id
    clip_dir.mkdir(parents=True, exist_ok=True)
    media_dir = clip_dir / "media"

    class_name = f"Scene_{clip_id}"
    script_path = clip_dir / f"_scene_llm_{clip_id}.py"
    script_path.write_text(script)

    fps = config["video"]["fps"]
    quality = "-qh" if fps >= 60 else "-qm"

    out_path = clip_dir / "_node_llm_custom.mp4"

    for stale in media_dir.rglob(f"{class_name}.mp4"):
        stale.unlink(missing_ok=True)

    result = subprocess.run(
        ["manim", quality, str(script_path.resolve()), class_name,
         "--media_dir", str(media_dir.resolve()), "--format", "mp4",
         "--disable_caching"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"manim render failed for llm_custom clip {clip_id}:\n"
            f"{result.stderr[-2000:]}"
        )

    outputs = sorted(media_dir.rglob(f"{class_name}.mp4"),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    if not outputs:
        raise FileNotFoundError(f"manim produced no {class_name}.mp4")

    outputs[0].rename(out_path)
    return out_path


register_renderer("manim_llm_custom", render_node)
