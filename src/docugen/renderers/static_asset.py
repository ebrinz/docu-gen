"""Static asset renderer — places images at layout positions."""
from __future__ import annotations
from pathlib import Path
from docugen.renderers import register_renderer

def render_node(node, inputs, clip, project_path):
    """Return path to source image. In fused mode this is handled inline
    by the fused renderer, so this only runs for unfused DAGs."""
    project_path = Path(project_path)
    asset = node.get("asset", "")
    images_dir = project_path / "images"
    asset_path = images_dir / asset
    if not asset_path.exists():
        raise FileNotFoundError(f"Asset not found: {asset_path}")
    return asset_path

register_renderer("static_asset", render_node)
