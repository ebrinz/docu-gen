"""Post-processing filter chain via ffmpeg (bloom, vignette, color grade)."""
from __future__ import annotations
import subprocess
import shutil
from pathlib import Path
from docugen.renderers import register_renderer

FILTER_PRESETS = {
    "bloom": "gblur=sigma=20[bloom];[0:v][bloom]blend=all_mode=screen:all_opacity=0.15",
    "vignette": "vignette=PI/5",
    "warm_grade": "colorbalance=rs=0.05:gs=-0.02:bs=-0.05",
    "cool_grade": "colorbalance=rs=-0.03:gs=0.02:bs=0.05",
    "sharpen": "unsharp=5:5:0.8",
}

def render_node(node, inputs, clip, project_path):
    """Apply filter chain to input video."""
    project_path = Path(project_path)
    clip_id = clip["clip_id"]
    clip_dir = project_path / "build" / "clips" / clip_id
    clip_dir.mkdir(parents=True, exist_ok=True)
    out_path = clip_dir / f"_node_{node['name']}.mp4"

    input_names = node.get("inputs", [])
    input_path = None
    for name in input_names:
        for part in name.split("+"):
            if part in inputs:
                input_path = inputs[part]
                break
        if input_path:
            break

    if not input_path:
        raise ValueError(f"No input resolved for post node '{node['name']}'")

    filters = node.get("filters", [])
    audio_nodes = node.get("audio", [])

    if not filters and not audio_nodes:
        shutil.copy2(input_path, out_path)
        return out_path

    filter_parts = []
    for f in filters:
        if f in FILTER_PRESETS:
            filter_parts.append(FILTER_PRESETS[f])
        else:
            filter_parts.append(f)

    cmd = ["ffmpeg", "-y", "-i", str(input_path)]
    for audio_name in audio_nodes:
        for part in audio_name.split("+"):
            if part in inputs:
                cmd.extend(["-i", str(inputs[part])])
    if filter_parts:
        cmd.extend(["-vf", ",".join(filter_parts)])
    cmd.append(str(out_path))

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg post failed: {result.stderr[-300:]}")
    return out_path

register_renderer("ffmpeg_post", render_node)
