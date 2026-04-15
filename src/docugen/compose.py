# src/docugen/compose.py
"""Compositing DAG orchestrator — walks render graphs, caches nodes, fuses Manim scenes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from docugen.renderers import get_renderer, discover_renderers


def topo_sort(nodes: list[dict]) -> list[dict]:
    """Topological sort of DAG nodes. Raises ValueError on cycles."""
    by_name = {n["name"]: n for n in nodes}
    in_degree = {n["name"]: 0 for n in nodes}
    adj: dict[str, list[str]] = {n["name"]: [] for n in nodes}

    for n in nodes:
        deps = set(n.get("refs", [])) | set(n.get("inputs", []))
        for dep in deps:
            for part in dep.split("+"):
                if part in by_name:
                    adj[part].append(n["name"])
                    in_degree[n["name"]] += 1

    queue = [name for name, deg in in_degree.items() if deg == 0]
    order = []

    while queue:
        queue.sort()
        name = queue.pop(0)
        order.append(by_name[name])
        for child in adj[name]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    if len(order) != len(nodes):
        raise ValueError("DAG contains a cycle")

    return order


def content_hash(node: dict, clip: dict, input_hashes: dict[str, str]) -> str:
    """Compute a content hash for a node based on its definition and inputs."""
    hasher = hashlib.sha256()
    node_data = {k: v for k, v in sorted(node.items()) if k != "name"}
    hasher.update(json.dumps(node_data, sort_keys=True, default=str).encode())
    clip_key = {
        "clip_id": clip.get("clip_id"),
        "word_times": clip.get("word_times"),
        "visuals": clip.get("visuals"),
        "timing": clip.get("timing"),
        "text": clip.get("text"),
    }
    hasher.update(json.dumps(clip_key, sort_keys=True, default=str).encode())
    for name in sorted(input_hashes):
        hasher.update(f"{name}:{input_hashes[name]}".encode())
    return hasher.hexdigest()[:16]


def _read_hash(hash_path: Path) -> str | None:
    if hash_path.exists():
        return hash_path.read_text().strip()
    return None


def _write_hash(hash_path: Path, h: str) -> None:
    hash_path.write_text(h)


def _detect_fusion_groups(nodes: list[dict]) -> list[list[dict]]:
    """Detect groups of manim nodes that can be fused into single scenes.

    manim_theme, manim_choreo, and static_asset nodes are all fusable
    into a single Manim Scene (static_asset gets inlined as ImageMobject).
    """
    fusable_types = {"manim_theme", "manim_choreo", "static_asset"}
    groups: list[list[dict]] = []
    current_group: list[dict] = []

    for node in nodes:
        if node["renderer"] in fusable_types:
            current_group.append(node)
        else:
            if current_group:
                groups.append(current_group)
                current_group = []
            groups.append([node])

    if current_group:
        groups.append(current_group)

    return groups


def render_clip_dag(
    clip: dict,
    dag: list[dict],
    project_path: Path,
    theme=None,
    force: bool = False,
) -> Path:
    """Render a clip by walking its DAG."""
    discover_renderers()

    project_path = Path(project_path)
    clip_id = clip["clip_id"]
    clip_dir = project_path / "build" / "clips" / clip_id
    clip_dir.mkdir(parents=True, exist_ok=True)

    sorted_nodes = topo_sort(dag)
    fusion_groups = _detect_fusion_groups(sorted_nodes)

    outputs: dict[str, Path] = {}
    hashes: dict[str, str] = {}

    for group in fusion_groups:
        if len(group) > 1:
            fused_name = "+".join(n["name"] for n in group)
            out_path = clip_dir / f"_node_{fused_name}.mp4"
            hash_path = clip_dir / f"_node_{fused_name}.hash"

            dep_hashes = {}
            for n in group:
                for dep in n.get("inputs", []):
                    for part in dep.split("+"):
                        if part in hashes:
                            dep_hashes[part] = hashes[part]

            group_hasher = hashlib.sha256()
            for n in group:
                group_hasher.update(content_hash(n, clip, dep_hashes).encode())
            group_hash = group_hasher.hexdigest()[:16]

            if not force and out_path.exists() and _read_hash(hash_path) == group_hash:
                for n in group:
                    outputs[n["name"]] = out_path
                    hashes[n["name"]] = group_hash
                outputs[fused_name] = out_path
                hashes[fused_name] = group_hash
                continue

            renderer = get_renderer("manim_fused")
            fused_node = {
                "name": fused_name,
                "renderer": "manim_fused",
                "nodes": group,
            }
            input_paths = {k: v for k, v in outputs.items()}
            result = renderer(fused_node, input_paths, clip, project_path, theme=theme)

            for n in group:
                outputs[n["name"]] = result
                hashes[n["name"]] = group_hash
            outputs[fused_name] = result
            hashes[fused_name] = group_hash
            _write_hash(hash_path, group_hash)

        else:
            node = group[0]
            name = node["name"]
            ext = "wav" if node["renderer"].startswith("audio_") else "mp4"
            if node["renderer"] == "static_asset":
                ext = "png"
            out_path = clip_dir / f"_node_{name}.{ext}"
            hash_path = clip_dir / f"_node_{name}.hash"

            dep_hashes = {}
            for dep in list(node.get("refs", [])) + list(node.get("inputs", [])):
                for part in dep.split("+"):
                    if part in hashes:
                        dep_hashes[part] = hashes[part]

            h = content_hash(node, clip, dep_hashes)

            if not force and out_path.exists() and _read_hash(hash_path) == h:
                outputs[name] = out_path
                hashes[name] = h
                continue

            input_paths = {}
            for dep in list(node.get("refs", [])) + list(node.get("inputs", [])):
                for part in dep.split("+"):
                    if part in outputs:
                        input_paths[part] = outputs[part]

            renderer = get_renderer(node["renderer"])
            if node["renderer"].startswith("manim_"):
                result = renderer(node, input_paths, clip, project_path, theme=theme)
            else:
                result = renderer(node, input_paths, clip, project_path)

            outputs[name] = result
            hashes[name] = h
            _write_hash(hash_path, h)

    last = sorted_nodes[-1]
    last_key = last["name"]
    if last_key in outputs:
        final_path = project_path / "build" / "clips" / f"{clip_id}.mp4"
        if final_path != outputs[last_key]:
            import shutil
            shutil.copy2(outputs[last_key], final_path)
        return final_path

    raise FileNotFoundError(f"No output for terminal node '{last_key}'")
