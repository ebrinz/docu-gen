"""Composite multiple video/image layers via ffmpeg alpha blending."""
from __future__ import annotations
import subprocess
import shutil
from pathlib import Path
from docugen.renderers import register_renderer

def render_node(node, inputs, clip, project_path):
    """Alpha-composite input layers in order."""
    project_path = Path(project_path)
    clip_id = clip["clip_id"]
    clip_dir = project_path / "build" / "clips" / clip_id
    clip_dir.mkdir(parents=True, exist_ok=True)
    out_path = clip_dir / f"_node_{node['name']}.mp4"

    input_names = node.get("inputs", [])
    input_paths = []
    for name in input_names:
        for part in name.split("+"):
            if part in inputs:
                p = inputs[part]
                if p not in input_paths:
                    input_paths.append(p)

    if not input_paths:
        raise ValueError(f"No inputs resolved for composite node '{node['name']}'")

    if len(input_paths) == 1:
        shutil.copy2(input_paths[0], out_path)
        return out_path

    filter_parts = []
    input_args = []
    for i, p in enumerate(input_paths):
        input_args.extend(["-i", str(p)])
    if len(input_paths) == 2:
        filter_str = "[0:v][1:v]overlay=format=auto"
    else:
        parts = []
        for i in range(1, len(input_paths)):
            base = f"[tmp{i-1}]" if i > 1 else "[0:v]"
            out_label = f"[tmp{i}]" if i < len(input_paths) - 1 else ""
            parts.append(f"{base}[{i}:v]overlay=format=auto{out_label}")
        filter_str = ";".join(parts)

    cmd = ["ffmpeg", "-y"] + input_args + ["-filter_complex", filter_str, str(out_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg composite failed: {result.stderr[-300:]}")
    return out_path

register_renderer("ffmpeg_composite", render_node)
