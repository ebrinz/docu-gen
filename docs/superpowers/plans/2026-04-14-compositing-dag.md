# Compositing DAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the monolithic Manim render pipeline with a compositing DAG that supports pluggable renderers, node-level caching, Manim fusion, and multi-tool creative workflows.

**Architecture:** Each clip's render is a DAG of nodes (theme bg, content, choreography, composite, post-process). An orchestrator walks the DAG, checks content-hash caches, fuses adjacent Manim nodes into single Scenes via `self.layers`, and dispatches each node to a registered renderer. Themes provide `default_dag()` templates and renderer methods instead of monolithic `build_scene()`.

**Tech Stack:** Python 3.10+, Manim Community, ffmpeg, hashlib (caching), importlib (renderer auto-discovery)

**Spec:** `docs/superpowers/specs/2026-04-14-compositing-dag-design.md`

---

### Task 1: Renderer Registry and Interface

**Files:**
- Create: `src/docugen/renderers/__init__.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_compose.py` with registry tests:

```python
# tests/test_compose.py
import pytest
from docugen.renderers import register_renderer, get_renderer, RENDERERS


def test_register_and_retrieve_renderer():
    def dummy(node, inputs, clip, project_path):
        return project_path / "out.mp4"

    register_renderer("test_dummy", dummy)
    assert get_renderer("test_dummy") is dummy


def test_get_unknown_renderer_raises():
    with pytest.raises(KeyError, match="no_such_renderer"):
        get_renderer("no_such_renderer")


def test_registry_rejects_non_callable():
    with pytest.raises(TypeError):
        register_renderer("bad", "not_a_function")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_compose.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'docugen.renderers'`

- [ ] **Step 3: Write the renderer registry**

```python
# src/docugen/renderers/__init__.py
"""Renderer plugin registry — auto-discovers and registers render node handlers."""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Callable, Protocol

from pathlib import Path as PathType


class RendererFn(Protocol):
    def __call__(
        self,
        node: dict,
        inputs: dict[str, PathType],
        clip: dict,
        project_path: PathType,
    ) -> PathType: ...


RENDERERS: dict[str, RendererFn] = {}


def register_renderer(name: str, fn: RendererFn) -> None:
    if not callable(fn):
        raise TypeError(f"Renderer must be callable, got {type(fn)}")
    RENDERERS[name] = fn


def get_renderer(name: str) -> RendererFn:
    if name not in RENDERERS:
        raise KeyError(f"Unknown renderer '{name}' — registered: {list(RENDERERS)}")
    return RENDERERS[name]


def discover_renderers() -> None:
    """Import all modules in this package to trigger registration."""
    pkg_dir = Path(__file__).parent
    for info in pkgutil.iter_modules([str(pkg_dir)]):
        if info.name.startswith("_"):
            continue
        importlib.import_module(f"docugen.renderers.{info.name}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_compose.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/docugen/renderers/__init__.py tests/test_compose.py
git commit -m "feat: renderer registry with auto-discovery"
```

---

### Task 2: DAG Walker and Content-Hash Caching (`compose.py`)

**Files:**
- Create: `src/docugen/compose.py`
- Modify: `tests/test_compose.py`

- [ ] **Step 1: Write failing tests for DAG operations**

Append to `tests/test_compose.py`:

```python
from pathlib import Path
from docugen.compose import topo_sort, content_hash, render_clip_dag


def test_topo_sort_linear():
    nodes = [
        {"name": "bg", "renderer": "manim_theme"},
        {"name": "choreo", "renderer": "manim_choreo", "refs": ["bg"]},
        {"name": "composite", "renderer": "ffmpeg_composite", "inputs": ["bg", "choreo"]},
    ]
    order = topo_sort(nodes)
    names = [n["name"] for n in order]
    assert names.index("bg") < names.index("choreo")
    assert names.index("choreo") < names.index("composite")


def test_topo_sort_detects_cycle():
    nodes = [
        {"name": "a", "renderer": "x", "refs": ["b"]},
        {"name": "b", "renderer": "x", "refs": ["a"]},
    ]
    with pytest.raises(ValueError, match="cycle"):
        topo_sort(nodes)


def test_content_hash_stable():
    node = {"name": "bg", "renderer": "manim_theme", "elements": ["hex_grid"]}
    clip = {"clip_id": "intro_01", "text": "hello"}
    h1 = content_hash(node, clip, input_hashes={})
    h2 = content_hash(node, clip, input_hashes={})
    assert h1 == h2


def test_content_hash_changes_on_node_change():
    clip = {"clip_id": "intro_01", "text": "hello"}
    h1 = content_hash({"name": "bg", "renderer": "manim_theme", "elements": ["hex_grid"]},
                       clip, input_hashes={})
    h2 = content_hash({"name": "bg", "renderer": "manim_theme", "elements": ["hex_grid", "particles"]},
                       clip, input_hashes={})
    assert h1 != h2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_compose.py::test_topo_sort_linear -v`
Expected: FAIL — `ImportError: cannot import name 'topo_sort' from 'docugen.compose'`

- [ ] **Step 3: Write compose.py**

```python
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
            # Handle fused names like "bg+choreo"
            for part in dep.split("+"):
                if part in by_name:
                    adj[part].append(n["name"])
                    in_degree[n["name"]] += 1

    queue = [name for name, deg in in_degree.items() if deg == 0]
    order = []

    while queue:
        queue.sort()  # deterministic ordering
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
    # Node definition (exclude name — same config under different name = same output)
    node_data = {k: v for k, v in sorted(node.items()) if k != "name"}
    hasher.update(json.dumps(node_data, sort_keys=True, default=str).encode())
    # Clip data relevant to this node
    clip_key = {
        "clip_id": clip.get("clip_id"),
        "word_times": clip.get("word_times"),
        "visuals": clip.get("visuals"),
        "timing": clip.get("timing"),
        "text": clip.get("text"),
    }
    hasher.update(json.dumps(clip_key, sort_keys=True, default=str).encode())
    # Input hashes
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

    Returns list of groups. Each group is a list of nodes that will be
    rendered as one fused Manim scene. Non-fusable nodes appear as
    single-element groups.
    """
    manim_types = {"manim_theme", "manim_choreo"}
    groups: list[list[dict]] = []
    current_group: list[dict] = []

    for node in nodes:
        if node["renderer"] in manim_types:
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
    """Render a clip by walking its DAG.

    Returns path to the final output (terminal node's output).
    """
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
            # Fused manim group
            fused_name = "+".join(n["name"] for n in group)
            ext = "mp4"
            out_path = clip_dir / f"_node_{fused_name}.{ext}"
            hash_path = clip_dir / f"_node_{fused_name}.hash"

            dep_hashes = {}
            for n in group:
                for dep in n.get("inputs", []):
                    for part in dep.split("+"):
                        if part in hashes:
                            dep_hashes[part] = hashes[part]

            # Hash all nodes in the group together
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
            # Pass theme for manim renderers
            if node["renderer"].startswith("manim_"):
                result = renderer(node, input_paths, clip, project_path, theme=theme)
            else:
                result = renderer(node, input_paths, clip, project_path)

            outputs[name] = result
            hashes[name] = h
            _write_hash(hash_path, h)

    # Return the last node's output as the clip's final file
    last = sorted_nodes[-1]
    last_key = last["name"]
    if last_key in outputs:
        # Copy/link to canonical clip output path
        final_path = project_path / "build" / "clips" / f"{clip_id}.mp4"
        if final_path != outputs[last_key]:
            import shutil
            shutil.copy2(outputs[last_key], final_path)
        return final_path

    raise FileNotFoundError(f"No output for terminal node '{last_key}'")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_compose.py -v`
Expected: All tests pass (topo_sort, content_hash, registry tests)

- [ ] **Step 5: Commit**

```bash
git add src/docugen/compose.py tests/test_compose.py
git commit -m "feat: DAG orchestrator with topo sort, content-hash caching, and fusion detection"
```

---

### Task 3: New ThemeBase Interface

**Files:**
- Modify: `src/docugen/themes/base.py`
- Modify: `tests/test_themes.py`

- [ ] **Step 1: Write failing tests for new interface**

Replace `tests/test_themes.py` with tests for both old and new interfaces:

```python
# tests/test_themes.py
import pytest
from docugen.themes import list_themes, load_theme


def test_list_themes_includes_biopunk():
    themes = list_themes()
    assert "biopunk" in themes


def test_load_theme_returns_theme_object():
    theme = load_theme("biopunk")
    assert theme.name == "biopunk"
    assert isinstance(theme.palette, dict)
    assert "bg" in theme.palette


def test_load_unknown_theme_raises():
    with pytest.raises(ValueError, match="Unknown theme"):
        load_theme("nonexistent")


def test_biopunk_manim_header_has_palette():
    theme = load_theme("biopunk")
    header = theme.manim_header()
    assert 'config.background_color' in header
    assert '#050510' in header
    assert 'def make_hex_grid' in header
    assert 'def alive_wait' in header


def test_biopunk_default_dag_returns_nodes():
    theme = load_theme("biopunk")
    clip = {
        "clip_id": "test_01",
        "visuals": {"slide_type": "data_text", "cue_words": [], "assets": []},
    }
    dag = theme.default_dag(clip)
    assert isinstance(dag, list)
    assert len(dag) >= 2
    names = [n["name"] for n in dag]
    assert "bg" in names
    assert "choreo" in names
    renderers = [n["renderer"] for n in dag]
    assert "manim_theme" in renderers
    assert "manim_choreo" in renderers


def test_biopunk_default_dag_includes_content_when_assets():
    theme = load_theme("biopunk")
    clip = {
        "clip_id": "test_02",
        "visuals": {
            "slide_type": "photo_organism",
            "assets": ["yeast.jpg"],
            "cue_words": [],
        },
    }
    dag = theme.default_dag(clip)
    names = [n["name"] for n in dag]
    assert "content" in names


def test_biopunk_default_dag_no_content_without_assets():
    theme = load_theme("biopunk")
    clip = {
        "clip_id": "test_03",
        "visuals": {"slide_type": "counter_sync", "cue_words": [], "assets": []},
    }
    dag = theme.default_dag(clip)
    names = [n["name"] for n in dag]
    assert "content" not in names


def test_biopunk_transition_sounds_returns_callables():
    theme = load_theme("biopunk")
    sounds = theme.transition_sounds()
    assert isinstance(sounds, dict)
    assert len(sounds) > 0
    for name, fn in sounds.items():
        assert callable(fn)


def test_biopunk_chapter_layers_returns_callables():
    theme = load_theme("biopunk")
    layers = theme.chapter_layers()
    assert isinstance(layers, dict)
    for name, fn in layers.items():
        assert callable(fn)
```

- [ ] **Step 2: Run tests to verify `default_dag` tests fail**

Run: `python -m pytest tests/test_themes.py::test_biopunk_default_dag_returns_nodes -v`
Expected: FAIL — `AttributeError: 'BiopunkTheme' object has no attribute 'default_dag'`

- [ ] **Step 3: Rewrite `base.py` with new interface**

Replace `src/docugen/themes/base.py` entirely:

```python
"""Abstract base class for docu-gen visual themes."""

from abc import ABC, abstractmethod
from pathlib import Path


class ThemeBase(ABC):
    name: str
    palette: dict[str, str]

    @abstractmethod
    def manim_header(self) -> str:
        """Return Manim preamble: imports, palette constants, helper functions."""

    @abstractmethod
    def default_dag(self, clip: dict) -> list[dict]:
        """Return the default DAG node list for a clip.

        Theme decides what layers a clip needs based on
        slide_type, assets, cue_words, etc. Can vary per clip.
        """

    @abstractmethod
    def render_theme_layer(self, elements: list[str]) -> str:
        """Return Manim code that sets up background elements.

        Returns indented code lines ready for a construct() body.
        Used by the fused manim renderer to compose scenes.
        """

    @abstractmethod
    def render_content_layer(self, assets: list[str], placement: str,
                             images_dir: str) -> str:
        """Return Manim code that places content assets.

        Returns indented code lines. Empty string if no assets.
        Used by the fused manim renderer to compose scenes.
        """

    @abstractmethod
    def render_choreography(self, clip: dict, duration: float,
                            images_dir: str) -> str:
        """Return Manim code for animation choreography.

        Receives the full clip dict including word_times and
        visuals.cue_words for word-level sync. When fused,
        can reference self.layers for cross-layer mobject access.

        Returns indented code lines.
        """

    @abstractmethod
    def transition_sounds(self) -> dict[str, callable]:
        """Return dict mapping sound names to audio generator functions."""

    @abstractmethod
    def chapter_layers(self) -> dict[str, callable]:
        """Return dict mapping layer names to drone layer generator functions."""
```

- [ ] **Step 4: Run tests to verify passing**

Run: `python -m pytest tests/test_themes.py -v`
Expected: All pass except `test_biopunk_default_dag_*` (biopunk hasn't implemented `default_dag` yet — will be added in Task 5). The interface tests (`test_load_theme_returns_theme_object`, `test_biopunk_manim_header_has_palette`, etc.) should still pass because the existing biopunk methods remain.

- [ ] **Step 5: Commit**

```bash
git add src/docugen/themes/base.py tests/test_themes.py
git commit -m "feat: new ThemeBase interface — default_dag, widened render_choreography"
```

---

### Task 4: Fused Manim Renderer

**Files:**
- Create: `src/docugen/renderers/manim_fused.py`
- Modify: `tests/test_compose.py`

This is the core renderer that takes a group of fused manim nodes (bg + content + choreo) and produces a single Manim Scene with `self.layers` for cross-layer references.

- [ ] **Step 1: Write failing test**

Append to `tests/test_compose.py`:

```python
from unittest.mock import patch, MagicMock
from docugen.renderers.manim_fused import build_fused_script


def test_build_fused_script_has_layers():
    clip = {
        "clip_id": "intro_01",
        "text": "hello world",
        "word_times": [{"word": "hello", "start": 0.0, "end": 0.5},
                       {"word": "world", "start": 0.5, "end": 1.0}],
        "visuals": {
            "slide_type": "data_text",
            "cue_words": [{"event": "show_text", "at_index": 0,
                           "params": {"text": "Hello World"}}],
            "assets": [],
        },
        "timing": {"clip_duration": 5.0},
    }
    nodes = [
        {"name": "bg", "renderer": "manim_theme",
         "elements": ["hex_grid", "imperial_border", "floating_bg"]},
        {"name": "choreo", "renderer": "manim_choreo", "refs": ["bg"]},
    ]
    from docugen.themes import load_theme
    theme = load_theme("biopunk")
    script = build_fused_script(nodes, clip, "/fake/images", theme, duration=5.0)

    assert "class Scene_intro_01" in script
    assert "self.layers" in script
    assert "make_hex_grid" in script
    assert "def construct" in script


def test_build_fused_script_with_content():
    clip = {
        "clip_id": "ch8_01",
        "text": "the sponge",
        "word_times": [{"word": "the", "start": 0.0, "end": 0.3},
                       {"word": "sponge", "start": 0.3, "end": 0.8}],
        "visuals": {
            "slide_type": "photo_organism",
            "cue_words": [{"event": "show_photo", "at_index": 1, "params": {}}],
            "assets": ["sponge.jpg"],
            "layout": "left",
        },
        "timing": {"clip_duration": 8.0},
    }
    nodes = [
        {"name": "bg", "renderer": "manim_theme",
         "elements": ["hex_grid", "imperial_border", "floating_bg"]},
        {"name": "content", "renderer": "static_asset",
         "asset": "sponge.jpg", "layout": "left"},
        {"name": "choreo", "renderer": "manim_choreo", "refs": ["bg", "content"]},
    ]
    from docugen.themes import load_theme
    theme = load_theme("biopunk")
    script = build_fused_script(nodes, clip, "/fake/images", theme, duration=8.0)

    assert "self.layers" in script
    assert "self.layers['content']" in script
    assert "sponge.jpg" in script
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_compose.py::test_build_fused_script_has_layers -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'docugen.renderers.manim_fused'`

- [ ] **Step 3: Write the fused renderer**

```python
# src/docugen/renderers/manim_fused.py
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

    # Start with theme header
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
            # Export theme objects to self.layers
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
                # Determine variable name from content layer
                var = "asset_0"
                script += f"        self.layers['{name}'] = {{'{var}': {var}}}\n\n"

        elif renderer_type == "manim_choreo":
            choreo_code = theme.render_choreography(clip, duration, images_dir)
            script += choreo_code + "\n"

    # Final hold with particle animation if available
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

    # Get duration
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

    # Clean stale cached renders
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_compose.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/docugen/renderers/manim_fused.py tests/test_compose.py
git commit -m "feat: fused Manim renderer with self.layers cross-layer refs"
```

---

### Task 5: Biopunk `default_dag()` and Rewritten Choreography

**Files:**
- Modify: `src/docugen/themes/biopunk.py`

This is the largest task — adding `default_dag()`, rewriting `_choreo_*` methods to use full clip data, and removing bespoke builders.

- [ ] **Step 1: Write failing test for choreography with word_times**

Append to `tests/test_compose.py`:

```python
def test_biopunk_choreo_counter_uses_word_times():
    from docugen.themes import load_theme
    theme = load_theme("biopunk")
    clip = {
        "clip_id": "intro_02",
        "text": "We found four hundred twenty compounds",
        "word_times": [
            {"word": "We", "start": 0.0, "end": 0.3},
            {"word": "found", "start": 0.3, "end": 0.6},
            {"word": "four", "start": 0.6, "end": 0.9},
            {"word": "hundred", "start": 0.9, "end": 1.2},
            {"word": "twenty", "start": 1.2, "end": 1.5},
            {"word": "compounds", "start": 1.5, "end": 2.0},
        ],
        "visuals": {
            "slide_type": "counter_sync",
            "cue_words": [
                {"event": "start_count", "at_index": 2,
                 "params": {"to": 420, "color": "gold", "label": "compounds"}},
            ],
            "assets": [],
        },
    }
    code = theme.render_choreography(clip, 5.0, "/fake")
    # Should wait until word at index 2 starts (0.6s)
    assert "0.6" in code or "self.wait" in code
    assert "420" in code


def test_biopunk_choreo_data_text_multiline():
    from docugen.themes import load_theme
    theme = load_theme("biopunk")
    clip = {
        "clip_id": "intro_03",
        "text": "one compound two billion ten years",
        "word_times": [
            {"word": "one", "start": 0.0, "end": 0.3},
            {"word": "compound", "start": 0.3, "end": 0.7},
            {"word": "two", "start": 0.7, "end": 1.0},
            {"word": "billion", "start": 1.0, "end": 1.3},
            {"word": "ten", "start": 1.3, "end": 1.6},
            {"word": "years", "start": 1.6, "end": 2.0},
        ],
        "visuals": {
            "slide_type": "data_text",
            "cue_words": [
                {"event": "show_text", "at_index": 0,
                 "params": {"text": "1 compound \u00b7 $2B \u00b7 10 years"}},
            ],
            "assets": [],
        },
    }
    code = theme.render_choreography(clip, 5.0, "/fake")
    assert "1 compound" in code or "item_" in code


def test_biopunk_choreo_organism_uses_layers():
    from docugen.themes import load_theme
    theme = load_theme("biopunk")
    clip = {
        "clip_id": "ch8_01",
        "text": "the sponge produces compounds",
        "word_times": [
            {"word": "the", "start": 0.0, "end": 0.2},
            {"word": "sponge", "start": 0.2, "end": 0.6},
            {"word": "produces", "start": 0.6, "end": 1.0},
            {"word": "compounds", "start": 1.0, "end": 1.5},
        ],
        "visuals": {
            "slide_type": "photo_organism",
            "cue_words": [
                {"event": "show_name", "at_index": 1,
                 "params": {"name": "Haliclona"}},
            ],
            "assets": ["sponge.jpg"],
            "layout": "left",
        },
    }
    code = theme.render_choreography(clip, 8.0, "/fake")
    assert "self.layers" in code
    assert "Haliclona" in code
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_compose.py::test_biopunk_choreo_counter_uses_word_times -v`
Expected: FAIL — current `render_choreography` signature is `(choreo_type, params, duration, images_dir)`, not `(clip, duration, images_dir)`

- [ ] **Step 3: Add `default_dag()` to biopunk**

Add this method to the `BiopunkTheme` class in `src/docugen/themes/biopunk.py`, after `render_content_layer`:

```python
    def default_dag(self, clip: dict) -> list[dict]:
        """Return the default DAG for a clip based on its slide type."""
        visuals = clip.get("visuals", {})
        slide_type = visuals.get("slide_type", "")
        assets = visuals.get("assets", [])

        nodes = [
            {"name": "bg", "renderer": "manim_theme",
             "elements": ["hex_grid", "imperial_border", "floating_bg"]},
        ]

        if assets:
            nodes.append({
                "name": "content", "renderer": "static_asset",
                "asset": assets[0],
                "layout": visuals.get("layout", "center"),
            })
            nodes.append({
                "name": "choreo", "renderer": "manim_choreo",
                "refs": ["bg", "content"],
            })
            fused_inputs = "bg+content+choreo"
        else:
            nodes.append({
                "name": "choreo", "renderer": "manim_choreo",
                "refs": ["bg"],
            })
            fused_inputs = "bg+choreo"

        nodes.append({
            "name": "composite", "renderer": "ffmpeg_composite",
            "inputs": [fused_inputs],
        })
        nodes.append({
            "name": "post", "renderer": "ffmpeg_post",
            "inputs": ["composite"],
            "filters": [],
        })

        return nodes
```

- [ ] **Step 4: Rewrite `render_choreography` to accept full clip**

Replace the existing `render_choreography` method and all `_choreo_*` methods. The new signature is `render_choreography(self, clip: dict, duration: float, images_dir: str) -> str`.

The new `render_choreography`:

```python
    def render_choreography(self, clip: dict, duration: float,
                            images_dir: str) -> str:
        """Return Manim code for animation choreography.

        Receives full clip dict with word_times and cue_words
        for word-level sync. Can reference self.layers when fused.
        """
        visuals = clip.get("visuals", {})
        slide_type = visuals.get("slide_type", "")
        cue_words = visuals.get("cue_words", [])
        word_times = clip.get("word_times", [])

        # Map slide types to choreography methods
        method_map = {
            "chapter_card": self._choreo_chapter_card,
            "counter_sync": self._choreo_counter,
            "data_text": self._choreo_data_text,
            "photo_organism": self._choreo_organism_reveal,
            "bar_chart_build": self._choreo_bar_chart,
            "before_after": self._choreo_before_after,
            "dot_merge": self._choreo_dot_merge,
            "remove_reveal": self._choreo_remove_reveal,
            "svg_reveal": self._choreo_svg_reveal,
            "ambient_field": self._choreo_ambient_field,
            "title": self._choreo_title,
            "fingerprint_compare": self._choreo_fingerprint_compare,
            "sonar_ring": self._choreo_sonar_ring,
            "anchor_drop": self._choreo_anchor_drop,
            "dot_field": self._choreo_dot_field,
        }

        method = method_map.get(slide_type)
        if method:
            return method(clip, duration, images_dir)
        return ""
```

- [ ] **Step 5: Rewrite `_choreo_counter` with word_times support**

Replace the existing `_choreo_counter` with:

```python
    def _choreo_counter(self, clip, duration, images_dir):
        visuals = clip.get("visuals", {})
        cue_words = visuals.get("cue_words", [])
        word_times = clip.get("word_times", [])

        count_time = 0.5
        count_to = 0
        count_color = palette["gold"]
        count_label = ""

        for cue in cue_words:
            if cue.get("event") == "start_count":
                idx = cue.get("at_index", 0)
                if idx < len(word_times):
                    count_time = word_times[idx]["start"]
                params = cue.get("params", {})
                count_to = params.get("to", 0)
                color_name = params.get("color", "gold")
                color_map = {"gold": palette["gold"], "cyan": palette["cyan"],
                             "green": palette["glow"], "red": palette["sith_red"]}
                count_color = color_map.get(color_name, palette["gold"])
                count_label = params.get("label", "")
                break

        try:
            count_val = int(str(count_to).replace(",", ""))
        except (ValueError, TypeError):
            count_val = 0

        label_code = ""
        if count_label:
            label_code = f'''
        lbl = Text("{count_label}", color=TEXT_DIM, font_size=36)
        lbl.next_to(counter, DOWN, buff=0.5)
        self.play(FadeIn(lbl), run_time=0.5)'''

        return f'''        # Counter sync: wait for cue at {count_time:.2f}s, count to {count_val}
        self.wait({count_time})
        counter = Integer(0, color="{count_color}").scale(4.5)
        self.add(counter)
{label_code}
        count_dur = min(2.5, {duration} - {count_time} - 1.5)
        self.play(
            counter.animate.set_value({count_val}),
            run_time=max(count_dur, 0.5),
            rate_func=rush_from,
        )
        self.play(counter.animate.scale(1.08), run_time=0.15)
        self.play(counter.animate.scale(1/1.08), run_time=0.3)
        hold = max({duration} - {count_time} - count_dur - 1.5, 0.3)
        alive_wait(self, hold, particles=bg)'''
```

- [ ] **Step 6: Rewrite `_choreo_data_text` with word_times + multi-line**

Replace the existing `_choreo_data_text` with:

```python
    def _choreo_data_text(self, clip, duration, images_dir):
        visuals = clip.get("visuals", {})
        cue_words = visuals.get("cue_words", [])
        word_times = clip.get("word_times", [])

        display_text = ""
        show_time = 0.2

        for cue in cue_words:
            if cue.get("event") == "show_text":
                display_text = cue.get("params", {}).get("text", "")
                idx = cue.get("at_index", 0)
                if idx < len(word_times):
                    show_time = word_times[idx].get("start", 0.2)
                break

        if not display_text:
            display_text = clip.get("text", "")

        display_text = display_text.replace('"', '\\\\"')

        has_bullets = "\u00b7" in display_text or "\\n" in display_text

        if has_bullets:
            items = [s.strip() for s in display_text.replace("\\n", "\u00b7").split("\u00b7") if s.strip()]
            items_code = ""
            for i, item in enumerate(items):
                items_code += f'''
        item_{i} = Text("{item}", color=TEXT_COL, font_size=48)
        if item_{i}.width > 10:
            item_{i}.scale(9.5 / item_{i}.width)
        items.add(item_{i})'''

            return f'''        # Data text (multi-line): show at {show_time:.2f}s
        self.wait({show_time})
        items = VGroup()
{items_code}
        items.arrange(DOWN, buff=0.5, aligned_edge=LEFT)
        items.move_to(ORIGIN)
        for i, item in enumerate(items):
            self.play(FadeIn(item, shift=RIGHT * 0.3), run_time=0.3)
            self.wait(0.15)
        alive_wait(self, max({duration} - {show_time} - len(items) * 0.45 - 1.0, 0.3), particles=bg)'''
        else:
            return f'''        # Data text: show at {show_time:.2f}s
        self.wait({show_time})
        txt = Text("{display_text}", color=TEXT_COL, font_size=64, weight=BOLD)
        if txt.width > 12:
            txt.scale(11.5 / txt.width)
        self.play(FadeIn(txt, shift=UP * 0.2), run_time=0.3)
        alive_wait(self, max({duration} - {show_time} - 1.0, 0.3), particles=bg)'''
```

- [ ] **Step 7: Rewrite `_choreo_organism_reveal` with self.layers + cue timing**

Replace the existing `_choreo_organism_reveal` with:

```python
    def _choreo_organism_reveal(self, clip, duration, images_dir):
        visuals = clip.get("visuals", {})
        cue_words = visuals.get("cue_words", [])
        word_times = clip.get("word_times", [])

        label_code_parts = []
        label_count = 0
        for cue in cue_words:
            event = cue.get("event", "")
            params = cue.get("params", {})
            idx = cue.get("at_index", 0)
            t = word_times[idx]["start"] if idx < len(word_times) else 0

            if event in ("show_name", "show_note", "show_structure"):
                text = params.get("name", params.get("note", params.get("structure", "")))
                color = {"show_name": palette["gold"], "show_note": palette["cyan"],
                         "show_structure": palette["purple"]}[event]
                i = label_count
                label_code_parts.append(f'''
        # Cue: {event} at {t:.2f}s
        current_time_{i} = self.renderer.time if hasattr(self.renderer, 'time') else 0
        wait_{i} = max(0, {t:.2f} - current_time_{i})
        if wait_{i} > 0:
            self.wait(wait_{i})
        lbl_{i} = Text("{text}", color="{color}", font_size=22)
        lbl_box_{i} = SurroundingRectangle(lbl_{i}, color="{color}",
                                            fill_color="{palette['bg']}", fill_opacity=0.85,
                                            buff=0.15, corner_radius=0.05)
        lbl_group_{i} = VGroup(lbl_box_{i}, lbl_{i})
        frame = self.layers.get('content', {{}}).get('asset_0', None)
        if frame:
            lbl_group_{i}.next_to(frame, RIGHT, buff=0.8).shift(DOWN * {i * 0.9 - 0.5})
            pointer_{i} = Line(
                frame.get_right() + RIGHT * 0.1,
                lbl_group_{i}.get_left() + LEFT * 0.1,
                color="{color}", stroke_width=1.5,
            )
            self.play(Create(pointer_{i}), FadeIn(lbl_group_{i}, shift=RIGHT * 0.2), run_time=0.8)
        else:
            lbl_group_{i}.move_to(RIGHT * 2 + DOWN * {i * 0.9 - 0.5})
            self.play(FadeIn(lbl_group_{i}, shift=RIGHT * 0.2), run_time=0.8)
        self.wait(0.3)''')
                label_count += 1

        labels_block = "\n".join(label_code_parts)
        hold = max(duration - 2.0 - label_count * 1.1, 0.5)

        return f'''        # Organism reveal with cue-synced labels
        # Labels reference self.layers['content'] for pointer positioning
{labels_block}
        alive_wait(self, {hold:.1f}, particles=bg)'''
```

- [ ] **Step 8: Rewrite `_choreo_title` to delegate to title tool**

Replace or add `_choreo_title`:

```python
    def _choreo_title(self, clip, duration, images_dir):
        """Title choreography — particle convergence reveal.

        The title tool generates its own complete Scene, but we need
        a code fragment for the fused renderer. Extract the construct()
        body from the title tool's output and return it.
        """
        from docugen.tools.title import build_title_script
        import json
        from pathlib import Path

        visuals = clip.get("visuals", {})
        cue_words = visuals.get("cue_words", [])
        params = {}
        for cue in cue_words:
            params.update(cue.get("params", {}))
        reveal_style = params.get("reveal_style", "particle")

        build_dir = Path(images_dir).parent / "build"
        plan_path = build_dir / "plan.json"
        if plan_path.exists():
            plan = json.loads(plan_path.read_text())
            meta = plan.get("meta", plan)
            title_text = meta.get("title", "Untitled")
            subtitle_text = meta.get("subtitle", "")
            plan_palette = meta.get("color_palette", {})
        else:
            title_text = "Untitled"
            subtitle_text = ""
            plan_palette = {}

        colors = {
            "bg": plan_palette.get("bg", palette["bg"]),
            "accent_gold": plan_palette.get("accent_gold", palette["gold"]),
            "accent_cyan": plan_palette.get("accent_cyan", palette["cyan"]),
            "glow": palette["glow"],
            "grid": palette["grid"],
            "text": plan_palette.get("text", palette["text"]),
        }

        font_dir = str(Path(__file__).resolve().parent.parent.parent.parent / "assets" / "fonts")
        full_script = build_title_script(title_text, subtitle_text, reveal_style,
                                         duration, colors, font_dir)

        # Extract the construct() body from the full script
        # The title tool produces: class Scene_title(Scene):\n    def construct(self):\n        ...
        # We need just the indented body after "def construct(self):"
        lines = full_script.split("\n")
        body_lines = []
        in_body = False
        for line in lines:
            if "def construct(self):" in line:
                in_body = True
                continue
            if in_body:
                body_lines.append(line)

        return "\n".join(body_lines) if body_lines else "        pass"

- [ ] **Step 9: Add `_choreo_ambient_field` and `_choreo_svg_reveal`**

```python
    def _choreo_ambient_field(self, clip, duration, images_dir):
        return f'''        # Ambient field — breathing pause
        line = Line(LEFT * 2, RIGHT * 2, color=GOLD, stroke_width=1, stroke_opacity=0.3)
        self.add(line)
        alive_wait(self, {duration:.1f}, particles=bg)'''

    def _choreo_svg_reveal(self, clip, duration, images_dir):
        # SVG assets are handled by the content layer — choreo just holds
        return f'''        # SVG reveal — content layer handles asset, choreo holds
        alive_wait(self, {max(duration - 2.0, 1.0):.1f}, particles=bg)'''
```

- [ ] **Step 10: Update remaining `_choreo_*` methods to new signature**

All remaining choreo methods (`_choreo_chapter_card`, `_choreo_fingerprint_compare`, `_choreo_sonar_ring`, `_choreo_anchor_drop`, `_choreo_dot_field`, `_choreo_remove_reveal`, `_choreo_dot_merge`, `_choreo_bar_chart`, `_choreo_before_after`) need their signature changed from `(self, params, duration, images_dir)` to `(self, clip, duration, images_dir)`.

For each, extract params from `clip["visuals"]["cue_words"]` instead of receiving them directly. Example for `_choreo_chapter_card`:

```python
    def _choreo_chapter_card(self, clip, duration, images_dir):
        visuals = clip.get("visuals", {})
        cue_words = visuals.get("cue_words", [])
        params = {}
        for cue in cue_words:
            params.update(cue.get("params", {}))
        num = params.get("num", "00")
        title = params.get("title", "UNTITLED")
        return f'''        # Chapter card
        ch_num = Text("{num}", font="Courier", color=SITH_RED, weight=BOLD).scale(1.5)
        ch_title = Text("{title}", font="Courier", color=GLOW, weight=BOLD).scale(0.9)
        ch_title.next_to(ch_num, RIGHT, buff=0.4)
        card = VGroup(ch_num, ch_title).move_to(ORIGIN)
        self.play(FadeIn(card, shift=RIGHT * 0.3), run_time=1.0)
        throb_title(self, ch_title, cycles=2, scale_factor=1.03, cycle_time=1.0)
        alive_wait(self, {max(duration - 4.0, 0.5):.1f}, particles=bg)'''
```

Apply the same pattern to all other `_choreo_*` methods — change signature, extract params from clip's cue_words. The animation code body stays the same.

- [ ] **Step 11: Remove all `_build_*_scene` bespoke builders**

Delete these methods from `BiopunkTheme`:
- `_build_title_scene` (lines 893-932)
- `_build_chapter_card_scene` (lines 934-966)
- `_build_data_text_scene` (lines 968-1042)
- `_build_ambient_field_scene` (lines 1044-1057)
- `_build_photo_organism_scene` (lines 1059-1146)
- `_build_counter_sync_scene` (lines 1148-1210)

- [ ] **Step 12: Run all tests**

Run: `python -m pytest tests/test_compose.py tests/test_themes.py -v`
Expected: All pass

- [ ] **Step 13: Commit**

```bash
git add src/docugen/themes/biopunk.py
git commit -m "feat: biopunk default_dag, rewritten choreo with word_times + self.layers, removed bespoke builders"
```

---

### Task 6: ffmpeg Composite and Post Renderers

**Files:**
- Create: `src/docugen/renderers/ffmpeg_composite.py`
- Create: `src/docugen/renderers/ffmpeg_post.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_compose.py`:

```python
def test_ffmpeg_composite_registered():
    from docugen.renderers import discover_renderers, get_renderer
    discover_renderers()
    fn = get_renderer("ffmpeg_composite")
    assert callable(fn)


def test_ffmpeg_post_registered():
    from docugen.renderers import discover_renderers, get_renderer
    discover_renderers()
    fn = get_renderer("ffmpeg_post")
    assert callable(fn)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_compose.py::test_ffmpeg_composite_registered -v`
Expected: FAIL — `KeyError: Unknown renderer 'ffmpeg_composite'`

- [ ] **Step 3: Write ffmpeg_composite renderer**

```python
# src/docugen/renderers/ffmpeg_composite.py
"""Composite multiple video/image layers via ffmpeg alpha blending."""

from __future__ import annotations

import subprocess
from pathlib import Path

from docugen.renderers import register_renderer


def render_node(node, inputs, clip, project_path):
    """Alpha-composite input layers in order."""
    project_path = Path(project_path)
    clip_id = clip["clip_id"]
    clip_dir = project_path / "build" / "clips" / clip_id
    clip_dir.mkdir(parents=True, exist_ok=True)
    out_path = clip_dir / f"_node_{node['name']}.mp4"

    # Resolve input paths — handle fused names like "bg+choreo"
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
        # Single input — just copy through
        import shutil
        shutil.copy2(input_paths[0], out_path)
        return out_path

    # Build ffmpeg filter for alpha overlay
    filter_parts = []
    input_args = []
    for i, p in enumerate(input_paths):
        input_args.extend(["-i", str(p)])
    # Overlay each subsequent input onto the first
    if len(input_paths) == 2:
        filter_str = "[0:v][1:v]overlay=format=auto"
    else:
        # Chain overlays: [0][1]overlay[tmp1]; [tmp1][2]overlay[tmp2]; ...
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
```

- [ ] **Step 4: Write ffmpeg_post renderer**

```python
# src/docugen/renderers/ffmpeg_post.py
"""Post-processing filter chain via ffmpeg (bloom, vignette, color grade)."""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path

from docugen.renderers import register_renderer


# Available filter presets
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

    # Resolve single input
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
        # No processing needed — pass through
        shutil.copy2(input_path, out_path)
        return out_path

    # Build filter chain
    filter_parts = []
    for f in filters:
        if f in FILTER_PRESETS:
            filter_parts.append(FILTER_PRESETS[f])
        else:
            filter_parts.append(f)

    cmd = ["ffmpeg", "-y", "-i", str(input_path)]

    # Add audio inputs if any
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
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_compose.py -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/docugen/renderers/ffmpeg_composite.py src/docugen/renderers/ffmpeg_post.py tests/test_compose.py
git commit -m "feat: ffmpeg composite and post-processing renderers"
```

---

### Task 7: Static Asset and Audio Synth Renderers

**Files:**
- Create: `src/docugen/renderers/static_asset.py`
- Create: `src/docugen/renderers/audio_synth.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_compose.py`:

```python
def test_static_asset_registered():
    from docugen.renderers import discover_renderers, get_renderer
    discover_renderers()
    fn = get_renderer("static_asset")
    assert callable(fn)


def test_audio_synth_registered():
    from docugen.renderers import discover_renderers, get_renderer
    discover_renderers()
    fn = get_renderer("audio_synth")
    assert callable(fn)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_compose.py::test_static_asset_registered -v`
Expected: FAIL

- [ ] **Step 3: Write static_asset renderer**

```python
# src/docugen/renderers/static_asset.py
"""Static asset renderer — places images at layout positions."""

from __future__ import annotations

from pathlib import Path

from docugen.renderers import register_renderer


def render_node(node, inputs, clip, project_path):
    """Place a static image asset. In fused mode this is handled inline
    by the fused renderer, so this only runs for unfused DAGs.

    Returns the path to the source image (no transformation needed
    when compositing handles positioning via ffmpeg overlay coordinates).
    """
    project_path = Path(project_path)
    asset = node.get("asset", "")
    images_dir = project_path / "images"
    asset_path = images_dir / asset

    if not asset_path.exists():
        raise FileNotFoundError(f"Asset not found: {asset_path}")

    return asset_path


register_renderer("static_asset", render_node)
```

- [ ] **Step 4: Write audio_synth renderer**

```python
# src/docugen/renderers/audio_synth.py
"""Audio synth renderer — generates per-clip cue sounds using numpy synthesis."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.io import wavfile

from docugen.renderers import register_renderer

_SR = 44100


def render_node(node, inputs, clip, project_path):
    """Generate audio cue sounds for a clip based on cue_words."""
    project_path = Path(project_path)
    clip_id = clip["clip_id"]
    clip_dir = project_path / "build" / "clips" / clip_id
    clip_dir.mkdir(parents=True, exist_ok=True)
    out_path = clip_dir / f"_node_{node['name']}.wav"

    visuals = clip.get("visuals", {})
    cue_words = visuals.get("cue_words", [])
    word_times = clip.get("word_times", [])
    timing = clip.get("timing", {})
    total_duration = timing.get("clip_duration", 5.0)

    # Generate silence for the full clip duration
    n_samples = int(total_duration * _SR)
    audio = np.zeros(n_samples, dtype=np.float32)

    # For now, produce silence — future renderers (audio_clap, audio_gen)
    # will generate actual cue sounds based on cue_words
    wavfile.write(str(out_path), _SR, audio)
    return out_path


register_renderer("audio_synth", render_node)
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_compose.py -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/docugen/renderers/static_asset.py src/docugen/renderers/audio_synth.py tests/test_compose.py
git commit -m "feat: static asset and audio synth renderers"
```

---

### Task 8: Simplify `tools/render.py` to Use Orchestrator

**Files:**
- Modify: `src/docugen/tools/render.py`
- Modify: `tests/test_render.py`

- [ ] **Step 1: Write failing test for new render path**

Replace `tests/test_render.py`:

```python
# tests/test_render.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from docugen.tools.render import render_all


def test_render_all_calls_compose(tmp_path):
    """Verify render_all dispatches to compose.render_clip_dag."""
    clips_data = {
        "title": "Test",
        "theme": "biopunk",
        "chapters": [{
            "id": "intro",
            "title": "Intro",
            "clips": [{
                "clip_id": "intro_01",
                "text": "Hello",
                "visuals": {"slide_type": "data_text", "cue_words": [], "assets": []},
                "timing": {"clip_duration": 5.0},
            }],
        }],
    }
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "clips.json").write_text(json.dumps(clips_data))
    (tmp_path / "images").mkdir()
    (tmp_path / "config.yaml").write_text("title: Test\n")

    with patch("docugen.tools.render.render_clip_dag") as mock_dag:
        mock_dag.return_value = tmp_path / "build" / "clips" / "intro_01.mp4"
        # Create the output so render_all sees it
        (tmp_path / "build" / "clips").mkdir(parents=True)
        (tmp_path / "build" / "clips" / "intro_01.mp4").write_text("fake")

        result = render_all(str(tmp_path))
        assert mock_dag.called
        assert "intro_01" in result
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_render.py::test_render_all_calls_compose -v`
Expected: FAIL — current render_all doesn't use compose

- [ ] **Step 3: Simplify render.py**

Replace the `_render_from_clips` and `render_clip` functions and update `render_all`:

```python
# At the top of render.py, add import:
from docugen.compose import render_clip_dag
from docugen.themes import load_theme

# Replace _render_from_clips:
def _render_from_clips(project_path: Path) -> str:
    """Render all clips from clips.json via compositing DAG."""
    config = load_config(project_path)
    clips_data = json.loads((project_path / "build" / "clips.json").read_text())
    theme_name = clips_data.get("theme", config.get("theme", "biopunk"))
    theme = load_theme(theme_name)

    results = []
    for i, chapter in enumerate(clips_data["chapters"]):
        ch_num = f"{i:02d}"
        ch_title = chapter.get("title", "").upper()
        for clip in chapter["clips"]:
            clip_id = clip["clip_id"]
            out_mp4 = project_path / "build" / "clips" / f"{clip_id}.mp4"
            if out_mp4.exists():
                results.append(f"{clip_id}.mp4 (exists)")
                continue
            try:
                dag = theme.default_dag(clip)
                render_clip_dag(clip, dag, project_path, theme=theme)
                results.append(f"{clip_id}.mp4 (rendered)")
            except Exception as e:
                results.append(f"{clip_id}.mp4 (FAILED: {e})")

    return "Rendered clips:\n" + "\n".join(results)
```

Keep `render_all`, `_get_wav_duration`, `PACING_BUFFER`, and the legacy `build_manim_script`/`render_chapter` functions for backwards compatibility with plan.json-based projects. Remove `build_clip_script`, `render_clip`, `_parse_direction`, and `ANIM_PRIMITIVES`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_render.py -v`
Expected: All pass. Note: legacy `test_build_manim_script_*` tests still pass because `build_manim_script` is unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/docugen/tools/render.py tests/test_render.py
git commit -m "feat: render.py dispatches to compositing DAG orchestrator"
```

---

### Task 9: Integration Test — Render a Real Clip

**Files:**
- Modify: `tests/test_compose.py`

- [ ] **Step 1: Write integration test**

Append to `tests/test_compose.py`:

```python
def test_render_clip_dag_produces_mp4(tmp_path):
    """Full integration: DAG walk -> fused manim render -> composite -> output."""
    from docugen.compose import render_clip_dag
    from docugen.themes import load_theme

    clip = {
        "clip_id": "test_int_01",
        "text": "There are sixty four thousand compounds.",
        "word_times": [
            {"word": "There", "start": 0.0, "end": 0.3},
            {"word": "are", "start": 0.3, "end": 0.5},
            {"word": "sixty", "start": 0.5, "end": 0.8},
            {"word": "four", "start": 0.8, "end": 1.0},
            {"word": "thousand", "start": 1.0, "end": 1.3},
            {"word": "compounds", "start": 1.3, "end": 1.8},
        ],
        "visuals": {
            "slide_type": "counter_sync",
            "cue_words": [
                {"event": "start_count", "at_index": 2,
                 "params": {"to": 64000, "color": "gold", "label": "compounds"}},
            ],
            "assets": [],
        },
        "timing": {"clip_duration": 5.0},
    }
    theme = load_theme("biopunk")
    dag = theme.default_dag(clip)

    # Set up minimal project structure
    (tmp_path / "images").mkdir()
    (tmp_path / "build" / "clips").mkdir(parents=True)
    (tmp_path / "config.yaml").write_text("title: Test\nvideo:\n  fps: 30\n  resolution: 720p\n")

    result = render_clip_dag(clip, dag, tmp_path, theme=theme)
    assert result.exists()
    assert result.suffix == ".mp4"
    assert result.stat().st_size > 0
```

- [ ] **Step 2: Run integration test**

Run: `python -m pytest tests/test_compose.py::test_render_clip_dag_produces_mp4 -v --timeout=120`
Expected: PASS — produces an actual MP4 with hex grid, border, particles, and animated counter

- [ ] **Step 3: Verify caching works**

```python
def test_render_clip_dag_caching(tmp_path):
    """Second render of same clip should skip cached nodes."""
    from docugen.compose import render_clip_dag
    from docugen.themes import load_theme
    import time

    clip = {
        "clip_id": "test_cache_01",
        "text": "hello",
        "word_times": [{"word": "hello", "start": 0.0, "end": 0.5}],
        "visuals": {
            "slide_type": "data_text",
            "cue_words": [{"event": "show_text", "at_index": 0,
                           "params": {"text": "Hello"}}],
            "assets": [],
        },
        "timing": {"clip_duration": 3.0},
    }
    theme = load_theme("biopunk")
    dag = theme.default_dag(clip)

    (tmp_path / "images").mkdir()
    (tmp_path / "build" / "clips").mkdir(parents=True)
    (tmp_path / "config.yaml").write_text("title: Test\nvideo:\n  fps: 30\n  resolution: 720p\n")

    # First render
    t1 = time.time()
    render_clip_dag(clip, dag, tmp_path, theme=theme)
    first_time = time.time() - t1

    # Second render (should be cached)
    t2 = time.time()
    render_clip_dag(clip, dag, tmp_path, theme=theme)
    second_time = time.time() - t2

    assert second_time < first_time * 0.5  # cached should be much faster
```

- [ ] **Step 4: Run caching test**

Run: `python -m pytest tests/test_compose.py::test_render_clip_dag_caching -v --timeout=120`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_compose.py
git commit -m "test: integration tests for DAG render and node-level caching"
```

---

### Task 10: Add `dag_template` to Slide Registry

**Files:**
- Modify: `src/docugen/themes/slides.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_slides.py`:

```python
def test_slide_registry_has_dag_hints():
    from docugen.themes.slides import SLIDE_REGISTRY
    # Slides with assets should hint at content node
    photo = SLIDE_REGISTRY["photo_organism"]
    assert "needs_content" in photo
    assert photo["needs_content"] is True

    # Slides without assets should not
    counter = SLIDE_REGISTRY["counter_sync"]
    assert counter.get("needs_content", False) is False
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_slides.py::test_slide_registry_has_dag_hints -v`
Expected: FAIL — `needs_content` not in registry entries

- [ ] **Step 3: Add `needs_content` field to relevant slide types**

In `src/docugen/themes/slides.py`, add `"needs_content": True` to slide types that use assets:

```python
    "photo_organism": {
        "description": "Photo inset with HUD border, animated pointer labels",
        "events": {"show_photo", "show_structure", "show_name", "show_note"},
        "params": {},
        "needs_content": True,
        "spans": [ ... ],
    },
    "svg_reveal": {
        "description": "SVG asset fades/draws in, Ken Burns drift, labels",
        "events": {"show_asset", "highlight_region", "show_label"},
        "params": {},
        "needs_content": True,
        "spans": [ ... ],
    },
```

Add `"needs_content": False` (or omit) to all other slide types.

- [ ] **Step 4: Run test**

Run: `python -m pytest tests/test_slides.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/docugen/themes/slides.py tests/test_slides.py
git commit -m "feat: add needs_content hint to slide registry for DAG generation"
```

---

### Task 11: Clean Old Render Tests and Run Full Suite

**Files:**
- Modify: `tests/test_render.py`

- [ ] **Step 1: Update test_render.py for removed functions**

Remove or update tests that reference `build_clip_script` and `render_clip` (which have been removed). Keep `test_build_manim_script_*` tests for legacy path. Update imports:

```python
# tests/test_render.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from docugen.tools.render import build_manim_script, render_all


def test_build_manim_script_intro():
    chapter = {
        "id": "intro",
        "title": "Introduction",
        "narration": "Welcome to this documentary.",
        "scene_type": "manim",
        "images": [],
        "duration_estimate": 10.0,
    }
    script = build_manim_script(
        chapter=chapter,
        doc_title="Test Documentary",
        duration=10.0,
        images_dir=Path("/fake/images"),
    )
    assert "class Scene_intro" in script
    assert "Test Documentary" in script


def test_build_manim_script_mixed_with_images():
    chapter = {
        "id": "ch1",
        "title": "Chapter One",
        "narration": "This chapter has images.",
        "scene_type": "mixed",
        "images": ["shot1.png", "diagram.jpg"],
        "duration_estimate": 30.0,
    }
    script = build_manim_script(
        chapter=chapter,
        doc_title="Test Documentary",
        duration=30.0,
        images_dir=Path("/fake/images"),
    )
    assert "class Scene_ch1" in script
    assert "shot1.png" in script


def test_build_manim_script_outro():
    chapter = {
        "id": "outro",
        "title": "Conclusion",
        "narration": "Thank you for watching.",
        "scene_type": "manim",
        "images": [],
        "duration_estimate": 12.0,
    }
    script = build_manim_script(
        chapter=chapter,
        doc_title="Test Documentary",
        duration=12.0,
        images_dir=Path("/fake/images"),
    )
    assert "class Scene_outro" in script


def test_render_all_calls_compose(tmp_path):
    clips_data = {
        "title": "Test",
        "theme": "biopunk",
        "chapters": [{
            "id": "intro",
            "title": "Intro",
            "clips": [{
                "clip_id": "intro_01",
                "text": "Hello",
                "visuals": {"slide_type": "data_text", "cue_words": [], "assets": []},
                "timing": {"clip_duration": 5.0},
            }],
        }],
    }
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "clips.json").write_text(json.dumps(clips_data))
    (tmp_path / "images").mkdir()
    (tmp_path / "config.yaml").write_text("title: Test\n")

    with patch("docugen.tools.render.render_clip_dag") as mock_dag:
        mock_dag.return_value = tmp_path / "build" / "clips" / "intro_01.mp4"
        (tmp_path / "build" / "clips").mkdir(parents=True, exist_ok=True)
        (tmp_path / "build" / "clips" / "intro_01.mp4").write_text("fake")
        result = render_all(str(tmp_path))
        assert mock_dag.called
```

- [ ] **Step 2: Run the full test suite**

Run: `python -m pytest tests/ -v --timeout=120`
Expected: All tests pass. Pay attention to `test_themes.py`, `test_render.py`, `test_slides.py`, `test_compose.py`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_render.py
git commit -m "test: update render tests for DAG-based pipeline"
```

---

### Task 12: Validation — Render Parse-Evols-Yeast Clips

**Files:** None (validation only)

- [ ] **Step 1: Clear existing rendered clips**

```bash
rm -f projects/parse-evols-yeast/build/clips/*.mp4
rm -rf projects/parse-evols-yeast/build/clips/*/
```

- [ ] **Step 2: Render all 82 clips via new DAG pipeline**

```bash
python -c "
from docugen.tools.render import render_all
result = render_all('projects/parse-evols-yeast')
print(result)
"
```

Expected: 82 clips rendered, zero failures. Each clip should now have a subdirectory with node artifacts:

```
build/clips/intro_01/
  _node_bg+choreo.mp4
  _node_bg+choreo.hash
  _node_composite.mp4
  ...
build/clips/intro_01.mp4
```

- [ ] **Step 3: Spot-check rendered clips for theme visuals**

Open 3-4 clips in a video player and verify:
- Hex grid visible in background
- Imperial border brackets visible
- Floating particles drifting
- Counter animations sync'd to correct timing (counter_sync clips)
- Text appears at correct cue word time (data_text clips)
- Photo organism clips show pointer labels

- [ ] **Step 4: Verify caching — re-run render**

```bash
python -c "
import time
from docugen.tools.render import render_all
t = time.time()
result = render_all('projects/parse-evols-yeast')
print(f'Time: {time.time()-t:.1f}s')
print(result)
"
```

Expected: All 82 clips show "(exists)" — cached, near-instant.

- [ ] **Step 5: Commit any fixes if needed, then final commit**

```bash
git add -A
git commit -m "feat: compositing DAG render pipeline — all 82 yeast clips render with full biopunk theme"
```
