# Sub-Clip Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor docu-gen from chapter-level to clip-level granularity with a 7-tool MCP pipeline, theme modules, auto-split with emotion tagging, and per-clip narration/rendering.

**Architecture:** Clips are the atomic unit. `split` tool breaks chapters into clips with emotion/pacing tags. Each downstream tool (narrate, render, score, stitch) operates on clips. Themes are pluggable Python modules providing all visual/audio identity.

**Tech Stack:** Python 3.12, FastMCP, Manim, Chatterbox MLX, scipy, numpy, ffmpeg, PyYAML

**Spec:** `docs/superpowers/specs/2026-04-12-subclip-architecture-design.md`

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `src/docugen/themes/__init__.py` | Theme registry: `list_themes()`, `load_theme(name)` |
| Create | `src/docugen/themes/base.py` | `ThemeBase` abstract class |
| Create | `src/docugen/themes/biopunk.py` | Biopunk Imperial theme (extracted from theme.py + scenes.py + score.py) |
| Create | `src/docugen/split.py` | Split algorithm: sentence parsing, clip boundaries, emotion tagging, pacing |
| Create | `src/docugen/tools/init_project.py` | Project setup tool |
| Create | `src/docugen/tools/score.py` | Score generation tool (extracted from stitch) |
| Modify | `src/docugen/config.py` | Add `theme` to defaults |
| Modify | `src/docugen/tools/narrate.py` | Refactor: read clips.json, per-clip WAV generation |
| Modify | `src/docugen/tools/render.py` | Refactor: read clips.json, theme-dispatched per-clip rendering |
| Modify | `src/docugen/tools/stitch.py` | Simplify: assembly only, no drone generation |
| Modify | `src/docugen/server.py` | 7 tools: init, plan, split, narrate, render, score, stitch |
| Create | `tests/test_split.py` | Split algorithm tests |
| Create | `tests/test_themes.py` | Theme registry + biopunk scene generation tests |
| Create | `tests/test_score.py` | Score tool tests (replaces test_drone.py) |
| Modify | `tests/test_narrate.py` | Adapt for clips.json input |
| Modify | `tests/test_config.py` | Add theme default test |
| Delete | `src/docugen/theme.py` | Replaced by themes/biopunk.py |
| Delete | `src/docugen/scenes.py` | Replaced by themes/biopunk.py |
| Delete | `src/docugen/score.py` | Moved to tools/score.py + themes/biopunk.py |

---

### Task 1: Theme Base Class + Registry

**Files:**
- Create: `src/docugen/themes/__init__.py`
- Create: `src/docugen/themes/base.py`
- Create: `tests/test_themes.py`

- [ ] **Step 1: Write failing test for theme registry**

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
    assert isinstance(theme.font, str)


def test_load_unknown_theme_raises():
    with pytest.raises(ValueError, match="Unknown theme"):
        load_theme("nonexistent")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_themes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'docugen.themes'`

- [ ] **Step 3: Create ThemeBase abstract class**

```python
# src/docugen/themes/base.py
"""Abstract base class for docu-gen visual themes."""

from abc import ABC, abstractmethod


class ThemeBase(ABC):
    name: str
    palette: dict[str, str]
    font: str

    @abstractmethod
    def manim_header(self) -> str:
        """Return Manim preamble code: imports, palette constants, helper functions."""

    @abstractmethod
    def idle_scene(self, duration: float) -> str:
        """Return Manim script for a blank themed slide with ambient motion."""

    @abstractmethod
    def chapter_card(self, num: str, title: str, duration: float) -> str:
        """Return Manim script for a chapter title card."""

    @abstractmethod
    def image_reveal(self, assets: list[str], direction: str,
                     duration: float, images_dir: str) -> str:
        """Return Manim script for image/SVG reveal with Ken Burns."""

    @abstractmethod
    def data_reveal(self, direction: str, duration: float) -> str:
        """Return Manim script for text/data appearing on screen."""

    @abstractmethod
    def custom_animation(self, direction: str, duration: float,
                         assets: list[str], images_dir: str) -> str:
        """Return Manim script for a custom animation sequence."""

    @abstractmethod
    def transition_sounds(self) -> dict[str, callable]:
        """Return dict mapping sound names to audio generator functions."""

    @abstractmethod
    def chapter_layers(self) -> dict[str, callable]:
        """Return dict mapping layer names to drone layer generator functions."""
```

- [ ] **Step 4: Create theme registry**

```python
# src/docugen/themes/__init__.py
"""Theme registry — discover and load visual themes."""

import importlib
import pkgutil
from pathlib import Path

from docugen.themes.base import ThemeBase


def list_themes() -> list[str]:
    """List available theme names by scanning the themes package."""
    themes_dir = Path(__file__).parent
    names = []
    for info in pkgutil.iter_modules([str(themes_dir)]):
        if info.name not in ("base", "__init__"):
            names.append(info.name)
    return sorted(names)


def load_theme(name: str) -> ThemeBase:
    """Load a theme module by name and return its theme instance."""
    available = list_themes()
    if name not in available:
        raise ValueError(f"Unknown theme '{name}'. Available: {available}")
    module = importlib.import_module(f"docugen.themes.{name}")
    return module.theme
```

- [ ] **Step 5: Create minimal biopunk stub (just enough to pass registry tests)**

```python
# src/docugen/themes/biopunk.py
"""Biopunk Imperial theme — stub for registry tests. Full implementation in Task 2."""

from docugen.themes.base import ThemeBase


class BiopunkTheme(ThemeBase):
    name = "biopunk"
    palette = {
        "bg": "#050510",
        "panel": "#0a0e1a",
        "glow": "#b8ffc4",
        "glow_dim": "#4a7a52",
        "purple": "#8b5cf6",
        "purple_deep": "#5b21b6",
        "purple_faint": "#3b1a6e",
        "sith_red": "#dc2626",
        "sith_red_dim": "#7f1d1d",
        "cyan": "#22d3ee",
        "gold": "#f59e0b",
        "text": "#e2e8f0",
        "text_dim": "#64748b",
        "grid": "#1a1a2e",
    }
    font = "Courier"

    def manim_header(self): return ""
    def idle_scene(self, duration): return ""
    def chapter_card(self, num, title, duration): return ""
    def image_reveal(self, assets, direction, duration, images_dir): return ""
    def data_reveal(self, direction, duration): return ""
    def custom_animation(self, direction, duration, assets, images_dir): return ""
    def transition_sounds(self): return {}
    def chapter_layers(self): return {}


theme = BiopunkTheme()
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_themes.py -v`
Expected: 3 PASS

- [ ] **Step 7: Commit**

```bash
git add src/docugen/themes/ tests/test_themes.py
git commit -m "feat: theme base class and registry with biopunk stub"
```

---

### Task 2: Biopunk Theme — Full Implementation

**Files:**
- Modify: `src/docugen/themes/biopunk.py`
- Modify: `tests/test_themes.py`
- Reference: `src/docugen/theme.py` (extract from), `src/docugen/scenes.py` (extract from), `src/docugen/score.py` (extract from)

- [ ] **Step 1: Write failing tests for biopunk scene generation**

Add to `tests/test_themes.py`:

```python
def test_biopunk_manim_header_has_palette():
    theme = load_theme("biopunk")
    header = theme.manim_header()
    assert 'config.background_color' in header
    assert '#050510' in header
    assert 'def make_hex_grid' in header
    assert 'def alive_wait' in header


def test_biopunk_idle_scene_valid_manim():
    theme = load_theme("biopunk")
    script = theme.idle_scene(10.0)
    assert 'class Scene_idle' in script
    assert 'def construct' in script


def test_biopunk_chapter_card_valid_manim():
    theme = load_theme("biopunk")
    script = theme.chapter_card("01", "THE PAPER", 5.0)
    assert 'class Scene_chapter_card' in script
    assert 'THE PAPER' in script


def test_biopunk_image_reveal_valid_manim():
    theme = load_theme("biopunk")
    script = theme.image_reveal(["test.svg"], "Fade in, zoom 1.04x", 8.0, "/tmp")
    assert 'class Scene_image_reveal' in script
    assert 'test.svg' in script


def test_biopunk_data_reveal_valid_manim():
    theme = load_theme("biopunk")
    script = theme.data_reveal("Show +16.4% in gold", 5.0)
    assert 'class Scene_data_reveal' in script


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

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_themes.py -v`
Expected: New tests FAIL (methods return empty strings)

- [ ] **Step 3: Implement full biopunk theme**

Extract and consolidate code from these existing files into `src/docugen/themes/biopunk.py`:

- **`manim_header()`**: Extract from `src/docugen/theme.py` — the `THEME_IMPORTS`, `THROB_TITLE`, `HEX_GRID`, `SCANLINE`, `PARTICLE_FIELD`, `IMPERIAL_BORDER`, `DNA_HELIX`, `AMBIENT_WAIT`, `FLOATING_DOTS` constants. Concatenate them all into the returned string.

- **`idle_scene(duration)`**: Generate a Manim script with the theme header + a scene class that has hex grid, floating bg, imperial border, and `alive_wait` for the full duration. This is the "blank slide."

- **`chapter_card(num, title, duration)`**: Generate a Manim script with theme header + scene that shows the chapter number in sith_red, title in glow with throb animation, imperial border, floating bg. Similar to the chapter card pattern in `src/docugen/scenes.py`.

- **`image_reveal(assets, direction, duration, images_dir)`**: Generate a Manim script that loads each asset as an `ImageMobject` or `SVGMobject`, applies Ken Burns motion (slow zoom 1.04x), with themed background. Duration split across assets.

- **`data_reveal(direction, duration)`**: Generate a Manim script that displays the `direction` text as styled `Text` mobjects on a themed background. For structured data (percentages, stats), use gold/glow colors.

- **`custom_animation(direction, duration, assets, images_dir)`**: Generate a Manim script with themed background and a placeholder scene. The `direction` field describes what to build — this method produces a themed container that can be hand-edited.

- **`transition_sounds()`**: Extract from `src/docugen/score.py` — the `TRANSITION_SOUNDS` dict and all `transition_*` functions (`transition_imperial_chime`, `transition_dark_swell`, `transition_crystal_ping`, `transition_heartbeat`, `transition_bell`, `transition_sonar`, `transition_resolve`, `transition_tension`).

- **`chapter_layers()`**: Extract from `src/docugen/score.py` — the `CHAPTER_LAYERS` dict and all `_layer_*` functions.

This file will be ~500-600 lines. That's acceptable — it contains all the creative/aesthetic code for one theme.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_themes.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/docugen/themes/biopunk.py tests/test_themes.py
git commit -m "feat: full biopunk Imperial theme implementation"
```

---

### Task 3: Config — Add Theme Default

**Files:**
- Modify: `src/docugen/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_config.py`:

```python
def test_load_config_has_theme_default(tmp_path):
    (tmp_path / "config.yaml").write_text("title: Test\n")
    cfg = load_config(tmp_path)
    assert cfg["theme"] == "biopunk"


def test_load_config_theme_override(tmp_path):
    (tmp_path / "config.yaml").write_text("title: Test\ntheme: corporate\n")
    cfg = load_config(tmp_path)
    assert cfg["theme"] == "corporate"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `KeyError: 'theme'`

- [ ] **Step 3: Add theme to DEFAULTS in config.py**

In `src/docugen/config.py`, add `"theme"` to the `DEFAULTS` dict:

```python
DEFAULTS = {
    "theme": "biopunk",
    "voice": {
        "engine": "openai",
        "model": "tts-1-hd",
        "voice": "echo",
    },
    "video": {
        "resolution": "1080p",
        "fps": 60,
    },
    "drone": {
        "cutoff_hz": 400,
        "duck_db": -18,
        "rt60": 1.5,
        "cue_freq": 220,
    },
}
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_config.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/docugen/config.py tests/test_config.py
git commit -m "feat: add theme field to config defaults"
```

---

### Task 4: Split Algorithm

**Files:**
- Create: `src/docugen/split.py`
- Create: `tests/test_split.py`

- [ ] **Step 1: Write failing tests for sentence splitting**

```python
# tests/test_split.py
import json
import pytest
from docugen.split import split_chapter, split_plan


def test_split_simple_chapter():
    """A short chapter with no assets becomes one chapter_card + one blank clip."""
    chapter = {
        "id": "intro",
        "title": "The Quest",
        "narration": "This is the beginning. The quest starts here.",
        "visuals": {"existing_svg": [], "source_images": []},
    }
    clips = split_chapter(chapter, default_exaggeration=0.5)
    assert len(clips) >= 2
    assert clips[0]["visuals"]["type"] == "chapter_card"
    assert clips[0]["clip_id"] == "intro_01"
    assert clips[1]["clip_id"] == "intro_02"


def test_split_long_narration_breaks_at_35_words():
    """Narration over 35 words gets split into multiple clips."""
    words = " ".join(["word"] * 40) + ". " + " ".join(["more"] * 40) + "."
    chapter = {
        "id": "ch1",
        "title": "Long",
        "narration": words,
        "visuals": {"existing_svg": [], "source_images": []},
    }
    clips = split_chapter(chapter, default_exaggeration=0.5)
    # chapter_card + at least 2 content clips
    content_clips = [c for c in clips if c["visuals"]["type"] != "chapter_card"]
    assert len(content_clips) >= 2
    for clip in content_clips:
        assert len(clip["text"].split()) <= 45  # some tolerance for keeping sentences together


def test_split_assigns_assets_to_clips():
    """Assets from visuals are distributed across clips positionally."""
    chapter = {
        "id": "ch2",
        "title": "Method",
        "narration": "First point here. Second point here. Third point here.",
        "visuals": {
            "existing_svg": ["fig1.svg", "fig2.svg"],
            "source_images": [],
        },
    }
    clips = split_chapter(chapter, default_exaggeration=0.3)
    asset_clips = [c for c in clips if c["visuals"]["assets"]]
    assert len(asset_clips) >= 1
    all_assets = []
    for c in asset_clips:
        all_assets.extend(c["visuals"]["assets"])
    assert "fig1.svg" in all_assets
    assert "fig2.svg" in all_assets


def test_split_emotion_tags_snark():
    """Sentences with snark markers get bumped exaggeration."""
    chapter = {
        "id": "ch3",
        "title": "Snarky",
        "narration": "This is a very long setup sentence about something technical and boring. Honestly.",
        "visuals": {"existing_svg": [], "source_images": []},
    }
    clips = split_chapter(chapter, default_exaggeration=0.2)
    content_clips = [c for c in clips if c["text"]]
    has_bump = any(c["exaggeration"] > 0.2 for c in content_clips)
    assert has_bump


def test_split_pacing_breathe_for_punchline():
    """Short sentence after long one gets 'breathe' pacing."""
    chapter = {
        "id": "ch4",
        "title": "Dramatic",
        "narration": "They tracked how many times each yeast cell divided before it died and out of two thousand compounds tested they found two that worked. Two.",
        "visuals": {"existing_svg": [], "source_images": []},
    }
    clips = split_chapter(chapter, default_exaggeration=0.3)
    # The "Two." sentence should be in a clip with breathe pacing
    punchline_clips = [c for c in clips if "Two." in c["text"]]
    assert any(c["pacing"] == "breathe" for c in punchline_clips)


def test_split_pacing_tight_for_lists():
    """Sequential short items get 'tight' pacing."""
    chapter = {
        "id": "ch5",
        "title": "Scale",
        "narration": "22,000 herbal compounds. 18,000 marine natural products. 18,000 pharmaceuticals. 900 nutraceuticals. 64,659 total.",
        "visuals": {"existing_svg": [], "source_images": []},
    }
    clips = split_chapter(chapter, default_exaggeration=0.3)
    tight_clips = [c for c in clips if c["pacing"] == "tight"]
    assert len(tight_clips) >= 1


def test_split_plan_produces_clips_json(tmp_path):
    """split_plan reads plan.json and writes clips.json."""
    plan = {
        "title": "Test",
        "chapters": [{
            "id": "intro",
            "title": "Intro",
            "narration": "Hello world.",
            "exaggeration": 0.5,
            "visuals": {"existing_svg": [], "source_images": []},
        }],
    }
    (tmp_path / "config.yaml").write_text("title: Test\ntheme: biopunk\n")
    build = tmp_path / "build"
    build.mkdir()
    (build / "plan.json").write_text(json.dumps(plan))

    result = split_plan(tmp_path)
    clips_path = build / "clips.json"
    assert clips_path.exists()
    clips_data = json.loads(clips_path.read_text())
    assert clips_data["theme"] == "biopunk"
    assert len(clips_data["chapters"]) == 1
    assert len(clips_data["chapters"][0]["clips"]) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_split.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement split.py**

Create `src/docugen/split.py` with:

- `_split_sentences(text)` — split text into sentences using punctuation boundaries (`. `, `? `, `! `). Handle abbreviations (Dr., Mr., etc.) and decimal numbers. Keep short follow-up sentences (< 5 words) attached to the preceding sentence if it's > 25 words.

- `_tag_emotion(text, base_exaggeration)` — scan for snark markers ("honestly", "apparently", "you're welcome", "by the way", etc.), short-after-long pattern, rhetorical questions, dramatic markers. Return `(exaggeration, emotion_tag)` tuple. Cap at 0.8.

- `_assign_pacing(text, prev_text)` — return `"tight"` for list items (< 8 words, preceded by similar-length item), `"breathe"` for short punchlines and rhetorical questions, `"normal"` otherwise.

- `split_chapter(chapter, default_exaggeration)` — core algorithm. Walk sentences, accumulate into clips, split on word count > 35 or asset boundaries. Assign visuals, emotion, pacing per clip. Return list of clip dicts.

- `split_plan(project_path)` — read `build/plan.json` and `config.yaml`, call `split_chapter` for each chapter, write `build/clips.json`. Return summary string.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_split.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/docugen/split.py tests/test_split.py
git commit -m "feat: split algorithm with emotion tagging and pacing"
```

---

### Task 5: Refactor Narrate — Per-Clip Generation

**Files:**
- Modify: `src/docugen/tools/narrate.py`
- Modify: `tests/test_narrate.py`

- [ ] **Step 1: Write failing test for clip-based narration**

Replace `test_generate_narration_chatterbox` in `tests/test_narrate.py` with:

```python
def test_generate_narration_from_clips(tmp_path):
    """Narrate reads clips.json and generates one WAV per clip."""
    import torch

    ref_wav = tmp_path / "ref.wav"
    ref_wav.write_bytes(_make_fake_wav())

    (tmp_path / "config.yaml").write_text(
        f"title: Test\n"
        f"voice:\n"
        f"  engine: chatterbox\n"
        f"  ref_audio: {ref_wav}\n"
        f"  exaggeration: 0.15\n"
        f"  cfg_weight: 0.8\n"
    )
    build = tmp_path / "build"
    build.mkdir()
    (build / "narration").mkdir()

    clips_data = {
        "title": "Test",
        "theme": "biopunk",
        "chapters": [{
            "id": "ch1",
            "title": "One",
            "clips": [
                {"clip_id": "ch1_01", "text": "Hello.", "exaggeration": 0.3,
                 "emotion_tag": "neutral", "pacing": "normal",
                 "visuals": {"type": "blank", "assets": [], "direction": ""}},
                {"clip_id": "ch1_02", "text": "World.", "exaggeration": 0.5,
                 "emotion_tag": "dramatic", "pacing": "breathe",
                 "visuals": {"type": "blank", "assets": [], "direction": ""}},
            ],
        }],
    }
    (build / "clips.json").write_text(json.dumps(clips_data))

    fake_tensor = torch.zeros(1, 24000 * 2)
    mock_model = MagicMock()
    mock_model.sr = 24000
    mock_model.generate.return_value = fake_tensor

    with patch("docugen.tools.narrate._get_chatterbox_model", return_value=mock_model):
        result = generate_narration(tmp_path)

    assert mock_model.generate.call_count == 2
    # Verify different exaggeration per clip
    calls = mock_model.generate.call_args_list
    assert calls[0][1]["exaggeration"] == 0.3
    assert calls[1][1]["exaggeration"] == 0.5

    assert (build / "narration" / "ch1_01.wav").exists()
    assert (build / "narration" / "ch1_02.wav").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_narrate.py::test_generate_narration_from_clips -v`
Expected: FAIL

- [ ] **Step 3: Refactor narrate.py**

Modify `generate_narration()` in `src/docugen/tools/narrate.py`:

- Check for `build/clips.json` first. If it exists, use clip-based generation. If not, fall back to `build/plan.json` chapter-based generation (backwards compatibility).
- For clip-based: iterate all clips across all chapters. For each clip, generate one WAV at `build/narration/{clip_id}.wav`. Pass each clip's `exaggeration` to the engine. Skip existing files.
- Keep all existing helper functions (`_generate_openai`, `_generate_chatterbox`, `_apply_post_fx`, `_get_chatterbox_model`).
- Modify `_generate_chatterbox` to accept `exaggeration` as a parameter (already done from earlier work).

- [ ] **Step 4: Run all narrate tests**

Run: `python -m pytest tests/test_narrate.py -v`
Expected: All PASS (old tests still work via plan.json fallback, new test uses clips.json)

- [ ] **Step 5: Commit**

```bash
git add src/docugen/tools/narrate.py tests/test_narrate.py
git commit -m "feat: refactor narrate for per-clip WAV generation"
```

---

### Task 6: Refactor Render — Per-Clip, Theme-Dispatched

**Files:**
- Modify: `src/docugen/tools/render.py`
- Modify: `tests/test_render.py`

- [ ] **Step 1: Write failing test for clip-based rendering**

```python
# Add to tests/test_render.py
import json
from unittest.mock import patch, MagicMock
from docugen.tools.render import build_clip_script


def test_build_clip_script_blank(tmp_path):
    """Blank clip produces a valid Manim script via theme."""
    clip = {
        "clip_id": "ch1_01",
        "text": "Hello.",
        "visuals": {"type": "blank", "assets": [], "direction": ""},
    }
    script = build_clip_script(clip, theme_name="biopunk",
                               duration=5.0, images_dir=str(tmp_path))
    assert "class Scene_ch1_01" in script
    assert "def construct" in script


def test_build_clip_script_chapter_card(tmp_path):
    """Chapter card clip uses theme's chapter_card method."""
    clip = {
        "clip_id": "ch2_01",
        "text": "",
        "visuals": {"type": "chapter_card", "assets": [], "direction": ""},
    }
    script = build_clip_script(clip, theme_name="biopunk",
                               duration=4.0, images_dir=str(tmp_path),
                               chapter_num="02", chapter_title="THE METHOD")
    assert "class Scene_ch2_01" in script
    assert "THE METHOD" in script


def test_build_clip_script_image_reveal(tmp_path):
    """Image reveal clip references the asset."""
    clip = {
        "clip_id": "ch3_02",
        "text": "Look at this.",
        "visuals": {"type": "image_reveal", "assets": ["fig.svg"],
                    "direction": "Fade in, zoom 1.04x"},
    }
    script = build_clip_script(clip, theme_name="biopunk",
                               duration=8.0, images_dir=str(tmp_path))
    assert "fig.svg" in script
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_render.py::test_build_clip_script_blank -v`
Expected: FAIL — `ImportError: cannot import name 'build_clip_script'`

- [ ] **Step 3: Implement clip-based render.py**

Refactor `src/docugen/tools/render.py`:

- Add `build_clip_script(clip, theme_name, duration, images_dir, chapter_num=None, chapter_title=None)` — loads the theme via `load_theme(theme_name)`, dispatches on `clip["visuals"]["type"]`:
  - `"blank"` → `theme.idle_scene(duration)`, then rename the class to `Scene_{clip_id}`
  - `"chapter_card"` → `theme.chapter_card(chapter_num, chapter_title, duration)`, rename class
  - `"image_reveal"` → `theme.image_reveal(assets, direction, duration, images_dir)`, rename class
  - `"data_reveal"` → `theme.data_reveal(direction, duration)`, rename class
  - `"animation"` → `theme.custom_animation(direction, duration, assets, images_dir)`, rename class

- Add `render_clip(project_path, clip, chapter_num, chapter_title)` — reads WAV duration for the clip, adds pacing buffer (tight +0.5, normal +1.5, breathe +3.5), generates script, runs manim, moves output to `build/clips/{clip_id}.mp4`.

- Refactor `render_all(project_path)` — check for `clips.json` first. If present, iterate clips and call `render_clip` for each. If not, fall back to old chapter-based rendering.

- Keep old `build_manim_script()` and scene functions for backwards compat but don't add to them.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_render.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/docugen/tools/render.py tests/test_render.py
git commit -m "feat: refactor render for per-clip theme-dispatched scenes"
```

---

### Task 7: Score Tool (Extracted from Stitch)

**Files:**
- Create: `src/docugen/tools/score.py`
- Create: `tests/test_score.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_score.py
import json
import struct
import numpy as np
import pytest
from pathlib import Path
from docugen.tools.score import generate_score


def _make_fake_wav(sr=24000, seconds=2):
    n = sr * seconds
    data_size = n * 2
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + data_size, b'WAVE',
        b'fmt ', 16, 1, 1, sr, sr * 2, 2, 16,
        b'data', data_size,
    )
    return header + b'\x00' * data_size


def test_generate_score_produces_wav(tmp_path):
    (tmp_path / "config.yaml").write_text("title: Test\ntheme: biopunk\n")
    build = tmp_path / "build"
    build.mkdir()
    narr = build / "narration"
    narr.mkdir()

    clips_data = {
        "title": "Test",
        "theme": "biopunk",
        "chapters": [{
            "id": "ch1",
            "title": "One",
            "clips": [
                {"clip_id": "ch1_01", "text": "Hello.", "exaggeration": 0.3,
                 "emotion_tag": "neutral", "pacing": "normal",
                 "visuals": {"type": "blank", "assets": [], "direction": ""}},
            ],
        }],
    }
    (build / "clips.json").write_text(json.dumps(clips_data))
    (narr / "ch1_01.wav").write_bytes(_make_fake_wav())

    result = generate_score(tmp_path)
    score_path = build / "score.wav"
    assert score_path.exists()
    assert score_path.stat().st_size > 0
    assert "score.wav" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_score.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement score tool**

Create `src/docugen/tools/score.py`:

- `generate_score(project_path)` — reads `build/clips.json` and clip WAV durations. Builds a chapter-level timeline (chapter start times from cumulative clip durations). Loads the theme for `transition_sounds()` and `chapter_layers()`. Uses base drone generation from `src/docugen/drone.py` (keep drone.py as the base engine — it's not theme-specific). Overlays theme's chapter layers and transition sounds. Writes `build/score.wav`. Returns summary string.

- The base drone engine (`drone.py`) stays unchanged — it provides `generate_drone_track()`, `pink_noise()`, `sine_wave()`, etc. The theme provides the chapter-specific overlays.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_score.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/docugen/tools/score.py tests/test_score.py
git commit -m "feat: standalone score tool with theme-driven layers"
```

---

### Task 8: Simplify Stitch — Assembly Only

**Files:**
- Modify: `src/docugen/tools/stitch.py`
- Modify: `tests/test_stitch.py`

- [ ] **Step 1: Write failing test for clip-based stitch**

```python
# Add to tests/test_stitch.py
import json

def test_stitch_reads_clips_json(tmp_path):
    """Stitch assembles from clips.json when present."""
    (tmp_path / "config.yaml").write_text("title: Test\ntheme: biopunk\n")
    build = tmp_path / "build"
    build.mkdir()

    clips_data = {
        "title": "Test",
        "theme": "biopunk",
        "chapters": [{
            "id": "ch1",
            "title": "One",
            "clips": [
                {"clip_id": "ch1_01", "text": "Hello.", "exaggeration": 0.3,
                 "emotion_tag": "neutral", "pacing": "normal",
                 "visuals": {"type": "blank", "assets": [], "direction": ""}},
            ],
        }],
    }
    (build / "clips.json").write_text(json.dumps(clips_data))

    # Create fake clip mp4 and narration wav and score wav
    # (These would be created by render, narrate, score tools)
    clips_dir = build / "clips"
    clips_dir.mkdir()
    narr_dir = build / "narration"
    narr_dir.mkdir()

    # Create minimal valid files (stitch will call ffmpeg which we mock)
    (clips_dir / "ch1_01.mp4").write_bytes(b"fake")
    (narr_dir / "ch1_01.wav").write_bytes(_make_fake_wav())
    (build / "score.wav").write_bytes(_make_fake_wav(sr=44100, seconds=3))

    # We can't easily test ffmpeg without mocking, so just verify
    # the concat file generation
    from docugen.tools.stitch import _build_concat_file
    concat = _build_concat_file(tmp_path, clips_data)
    assert "ch1_01.mp4" in concat.read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stitch.py -v`
Expected: FAIL — `ImportError: cannot import name '_build_concat_file'`

- [ ] **Step 3: Refactor stitch.py**

Simplify `src/docugen/tools/stitch.py`:

- Add `_build_concat_file(project_path, clips_data)` — generates ffmpeg concat file from clip IDs in order. Returns the path.
- Refactor `stitch_all()`:
  - Check for `clips.json` first. If present, use clip-based assembly.
  - Build voice track from `build/narration/{clip_id}.wav` files placed at correct offsets.
  - Load `build/score.wav` (pre-generated by score tool) instead of calling `generate_drone_track()`.
  - Mix voice + score with ducking (keep existing `mix_audio` function).
  - Concatenate clips, mux audio, output `build/final.mp4`.
  - Fall back to old chapter-based path if no clips.json.
- Remove the `generate_drone_track` import and inline drone generation — that's now the score tool's job.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_stitch.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/docugen/tools/stitch.py tests/test_stitch.py
git commit -m "feat: simplify stitch to assembly-only with clips.json support"
```

---

### Task 9: Init Tool

**Files:**
- Create: `src/docugen/tools/init_project.py`

- [ ] **Step 1: Implement init tool**

```python
# src/docugen/tools/init_project.py
"""Init tool: create a new project directory with theme selection."""

import json
from pathlib import Path
import yaml

from docugen.themes import list_themes


def init_project(project_name: str, theme: str = "biopunk") -> str:
    """Create a new project directory with starter files.

    Args:
        project_name: Name for the project (used as directory name).
        theme: Theme module name. Defaults to 'biopunk'.

    Returns:
        Summary string with project path and contents.
    """
    project_path = Path("projects") / project_name
    if project_path.exists():
        return f"Project already exists: {project_path}"

    project_path.mkdir(parents=True)
    (project_path / "images").mkdir()
    (project_path / "build").mkdir()

    available = list_themes()
    if theme not in available:
        theme = "biopunk"

    config = {
        "title": project_name.replace("-", " ").replace("_", " ").title(),
        "theme": theme,
        "voice": {
            "engine": "openai",
            "model": "tts-1-hd",
            "voice": "echo",
        },
        "video": {
            "resolution": "1080p",
            "fps": 60,
        },
        "drone": {
            "cutoff_hz": 400,
            "duck_db": -18,
            "rt60": 1.5,
        },
    }
    with open(project_path / "config.yaml", "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    (project_path / "prompt.txt").write_text(
        "Create a clear, engaging documentary that explains the key concepts.\n"
        "Use a calm, authoritative tone. Break into logical chapters.\n"
    )

    lines = [
        f"Project created: {project_path}",
        f"Theme: {theme}",
        f"Available themes: {', '.join(available)}",
        "",
        "Next steps:",
        "  1. Add spec.pdf and images to the project directory",
        "  2. Edit prompt.txt with creative direction",
        "  3. Run: plan -> split -> narrate -> render -> score -> stitch",
    ]
    return "\n".join(lines)
```

- [ ] **Step 2: Commit**

```bash
git add src/docugen/tools/init_project.py
git commit -m "feat: init tool for project setup with theme selection"
```

---

### Task 10: Update Server — 7 Tools

**Files:**
- Modify: `src/docugen/server.py`

- [ ] **Step 1: Rewrite server.py with all 7 tools**

```python
# src/docugen/server.py
"""Docugen MCP Server — documentary generation pipeline."""

from mcp.server.fastmcp import FastMCP

from docugen.tools.init_project import init_project
from docugen.tools.plan import extract_pdf_text, generate_plan
from docugen.split import split_plan
from docugen.tools.narrate import generate_narration
from docugen.tools.render import render_all
from docugen.tools.score import generate_score
from docugen.tools.stitch import stitch_all

mcp = FastMCP("docugen", instructions=(
    "Documentary generation pipeline. Use tools in order: "
    "init → plan → split → narrate → render → score → stitch. "
    "Review artifacts between stages. "
    "Edit clips.json to adjust emotion, pacing, and visuals before narrate."
))


@mcp.tool()
def init(project_name: str, theme: str = "biopunk") -> str:
    """Create a new project directory with theme selection.

    Sets up the project structure with config.yaml, images/,
    and prompt.txt. Lists available themes.

    Args:
        project_name: Name for the project directory.
        theme: Visual theme module name (default: biopunk).
    """
    return init_project(project_name, theme)


@mcp.tool()
def plan(project_path: str) -> str:
    """Extract text from spec.pdf and generate a chapter plan via AI.

    Creates build/plan.json with chapter structure, narration scripts,
    and image assignments. Review and edit plan.json before proceeding.

    Args:
        project_path: Path to project directory containing config.yaml,
                      spec.pdf, prompt.txt, and images/
    """
    pdf_text = extract_pdf_text(f"{project_path}/spec.pdf")
    return generate_plan(project_path, pdf_text=pdf_text)


@mcp.tool()
def split(project_path: str) -> str:
    """Split chapters into clips with emotion tagging and pacing.

    Reads build/plan.json, produces build/clips.json. Each clip gets:
    - Narration text (1-3 sentences)
    - Emotion exaggeration (auto-tagged from text patterns)
    - Pacing (tight/normal/breathe)
    - Visual assignment (type + assets + direction)

    Edit clips.json to adjust before running narrate.

    Args:
        project_path: Path to project directory.
    """
    return split_plan(project_path)


@mcp.tool()
def narrate(project_path: str) -> str:
    """Generate TTS narration audio for each clip.

    Reads build/clips.json (or build/plan.json for legacy projects).
    Creates build/narration/{clip_id}.wav with per-clip emotion.
    Skips existing files for incremental re-generation.

    Args:
        project_path: Path to project directory.
    """
    return generate_narration(project_path)


@mcp.tool()
def render(project_path: str) -> str:
    """Render Manim video scenes for each clip.

    Reads build/clips.json and narration WAV durations.
    Creates build/clips/{clip_id}.mp4 using the project's theme.
    Skips existing files for incremental re-generation.

    Args:
        project_path: Path to project directory.
    """
    return render_all(project_path)


@mcp.tool()
def score(project_path: str) -> str:
    """Generate the drone score with chapter-specific layers.

    Reads build/clips.json and narration WAV durations.
    Creates build/score.wav with per-chapter drone layers
    and transition sounds from the project's theme.

    Args:
        project_path: Path to project directory.
    """
    return generate_score(project_path)


@mcp.tool()
def stitch(project_path: str) -> str:
    """Assemble clips, narration, and score into final video.

    Concatenates build/clips/*.mp4, mixes narration with score
    (voice-activated ducking), outputs build/final.mp4.

    Args:
        project_path: Path to project directory.
    """
    return stitch_all(project_path)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add src/docugen/server.py
git commit -m "feat: 7-tool MCP server — init, plan, split, narrate, render, score, stitch"
```

---

### Task 11: Cleanup — Delete Old Files

**Files:**
- Delete: `src/docugen/theme.py`
- Delete: `src/docugen/scenes.py`
- Delete: `src/docugen/score.py`
- Modify: `tests/test_drone.py` (keep — drone.py stays as base engine)

- [ ] **Step 1: Verify no remaining imports of old files**

Run:
```bash
grep -r "from docugen.theme import\|from docugen.scenes import\|from docugen.score import" src/ tests/
```
Expected: No matches (all references should now point to `docugen.themes` or `docugen.tools.score`)

- [ ] **Step 2: Delete old files**

```bash
rm src/docugen/theme.py src/docugen/scenes.py src/docugen/score.py
```

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove old theme.py, scenes.py, score.py — replaced by themes/ and tools/score.py"
```

---

### Task 12: Integration Test — End-to-End with parse-evols-yeast

**Files:**
- No new files — uses existing project

- [ ] **Step 1: Run split on the existing project**

```bash
python -c "from docugen.split import split_plan; print(split_plan('projects/parse-evols-yeast'))"
```

Verify `build/clips.json` is created with sensible clip boundaries, emotion tags, and pacing.

- [ ] **Step 2: Inspect clips.json**

Spot-check:
- ch5_dark clips have low exaggeration and `deadpan` tags
- ch7_synergy's "You're welcome" clip has bumped exaggeration and `punchline` tag
- ch8_organisms has separate clips per organism with `image_reveal` types
- List sequences in ch3_scale have `tight` pacing
- "Two." punchline in ch1_paper has `breathe` pacing

- [ ] **Step 3: Run narrate on one clip to verify**

```bash
python -c "
from docugen.tools.narrate import generate_narration
# Only narrate first 2 clips by temporarily trimming clips.json
print(generate_narration('projects/parse-evols-yeast'))
" 2>&1 | head -20
```

Verify per-clip WAVs appear in `build/narration/` with clip_id naming.

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "test: verify sub-clip pipeline on parse-evols-yeast project"
```
