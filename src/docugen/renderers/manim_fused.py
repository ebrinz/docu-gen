"""Fused Manim renderer — combines multiple manim nodes into a single Scene."""

from __future__ import annotations

import subprocess
from pathlib import Path

from docugen.config import load_config
from docugen.renderers import register_renderer


def build_fused_script(
    nodes: list[dict],
    clip: dict,
    images_dir: str,
    theme,
    duration: float,
) -> str:
    """Build a single Manim script from multiple fused nodes.
    Uses self.layers as the shared namespace between layers.
    """
    clip_id = clip["clip_id"]
    visuals = clip.get("visuals", {})
    assets = visuals.get("assets", [])
    placement = visuals.get("layout", "center")

    script = theme.manim_header()
    script += f"\n\nclass Scene_{clip_id}(Scene):\n"
    script += "    def construct(self):\n"
    script += "        self.layers = {}\n\n"

    for node in nodes:
        renderer_type = node["renderer"]
        name = node["name"]
        script += f"        # === Layer: {name} ({renderer_type}) ===\n"

        if renderer_type == "manim_theme":
            elements = node.get("elements", ["hex_grid", "imperial_border", "floating_bg"])
            theme_code = theme.render_theme_layer(elements)
            script += theme_code + "\n"
            exports = []
            if "hex_grid" in elements:
                exports.append("'grid': grid")
            if "floating_bg" in elements:
                exports.append("'particles': bg")
            if "imperial_border" in elements:
                exports.append("'border': border")
            if exports:
                script += f"        self.layers['{name}'] = {{{', '.join(exports)}}}\n\n"

        elif renderer_type == "static_asset":
            asset = node.get("asset", assets[0] if assets else "")
            layout = node.get("layout", placement)
            content_code = theme.render_content_layer(
                [asset] if asset else [], layout, images_dir)
            if content_code:
                script += content_code + "\n"
                var = "asset_0"
                script += f"        self.layers['{name}'] = {{'{var}': {var}}}\n\n"

        elif renderer_type == "manim_choreo":
            # Detect whether theme uses the new (clip, duration, images_dir) signature
            # or the old (choreo_type, params, duration, images_dir) signature.
            # Task 5 will rewrite biopunk to the new signature; until then we bridge.
            import inspect
            sig = inspect.signature(theme.render_choreography)
            n_params = len(sig.parameters)
            if n_params == 3:
                choreo_code = theme.render_choreography(clip, duration, images_dir)
            else:
                # Old signature: (choreo_type, params, duration, images_dir)
                # Extract the slide_type string so the dict isn't passed as a key;
                # most clip types won't be in the old method_map so this safely returns "".
                slide_type = clip.get("visuals", {}).get("slide_type", "")
                params = clip.get("visuals", {}).get("cue_words", [{}])[0].get("params", {})
                choreo_code = theme.render_choreography(slide_type, params, duration, images_dir)
            script += choreo_code + "\n"

    hold_time = max(duration * 0.1, 0.3)
    has_bg = any(
        "floating_bg" in n.get("elements", [])
        for n in nodes if n["renderer"] == "manim_theme"
    )
    if has_bg:
        script += f"        alive_wait(self, {hold_time:.1f}, particles=bg)\n"
    else:
        script += f"        self.wait({hold_time:.1f})\n"

    return script


def render_node(node, inputs, clip, project_path, theme=None):
    """Render a fused group of manim nodes to a single MP4."""
    project_path = Path(project_path)
    config = load_config(project_path)
    clip_id = clip["clip_id"]
    images_dir = str(project_path / "images")
    clips_dir = project_path / "build" / "clips" / clip_id
    clips_dir.mkdir(parents=True, exist_ok=True)
    media_dir = clips_dir / "media"

    fused_name = node["name"]
    sub_nodes = node["nodes"]
    out_path = clips_dir / f"_node_{fused_name}.mp4"

    timing = clip.get("timing", {})
    duration = timing.get("clip_duration", 0)
    if duration <= 0:
        from docugen.tools.render import _get_wav_duration, PACING_BUFFER
        wav_path = project_path / "build" / "narration" / f"{clip_id}.wav"
        if wav_path.exists():
            duration = _get_wav_duration(wav_path)
        else:
            duration = 3.0
        pacing = clip.get("pacing", "normal")
        duration += PACING_BUFFER.get(pacing, 1.5)

    script = build_fused_script(sub_nodes, clip, images_dir, theme, duration)

    class_name = f"Scene_{clip_id}"
    script_path = clips_dir / f"_scene_{clip_id}.py"
    script_path.write_text(script)

    fps = config["video"]["fps"]
    quality = "-qh" if fps >= 60 else "-qm"

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
            f"Manim render failed for {clip_id}:\n{result.stderr[-500:]}")

    output_files = sorted(
        media_dir.rglob(f"{class_name}.mp4"),
        key=lambda p: p.stat().st_mtime, reverse=True)
    if not output_files:
        raise FileNotFoundError(f"Manim output not found for {class_name}")

    output_files[0].rename(out_path)
    return out_path


register_renderer("manim_fused", render_node)
