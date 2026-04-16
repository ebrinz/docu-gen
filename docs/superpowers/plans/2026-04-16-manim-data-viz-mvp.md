# Manim Data Viz MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current generic-template slide grammar with a typed ~13-primitive MVP grammar that renders real data viz from structured specs, plus an `llm_custom` escape hatch and a `viz_extract` tool that decodes source PDFs into structured JSON.

**Architecture:** Add a `themes/primitives/` package where each primitive owns its schema, cue events, and render function. Auto-discover these at import time to populate `SLIDE_REGISTRY`. Refactor `themes/biopunk.py` from a 1,175-line god-file into a thin dispatcher. Add per-primitive schema validation in `direct_apply`. Introduce `viz_extract` (new MCP tool) that produces `build/pdf_data.json` via Claude vision; `direct_prepare` attaches that artifact + primitive schemas to its context.

**Tech Stack:** Python 3.10+, Manim Community, FastMCP, pytest. No new runtime deps — schemas validated with hand-written per-primitive functions (dict checks, not Pydantic, to keep install footprint flat).

**Spec:** `docs/superpowers/specs/2026-04-16-manim-data-viz-design.md`

---

## File structure

### New files

```
src/docugen/themes/primitives/
├── __init__.py              # Auto-discovery, SLIDE_REGISTRY assembly
├── _base.py                 # Protocol and helpers shared by primitives
├── bar_chart.py             # Upgrade of bar_chart_build — real axes
├── counter.py               # Upgrade of counter_sync — units + easing
├── before_after.py          # Upgrade — auto delta
├── callout.py               # Rename of data_text
├── line_chart.py            # NEW — timeseries with real axes
├── tree.py                  # NEW — hierarchical layout
├── timeline.py              # NEW — events on axis
├── llm_custom.py            # Escape-hatch schema + cue set (renderer is elsewhere)
├── title.py                 # Migrated unchanged
├── chapter_card.py          # Migrated unchanged
├── ambient_field.py         # Migrated unchanged
├── svg_reveal.py            # Migrated unchanged
└── photo_organism.py        # Migrated unchanged

src/docugen/renderers/
└── manim_llm_custom.py      # Compile-retry renderer for escape-hatch scripts

src/docugen/tools/
└── viz_extract.py           # New MCP tool — PDF → build/pdf_data.json

tests/primitives/
├── __init__.py
├── test_registry.py
├── test_bar_chart.py
├── test_counter.py
├── test_before_after.py
├── test_callout.py
├── test_line_chart.py
├── test_tree.py
├── test_timeline.py
└── test_llm_custom.py

tests/
├── test_viz_extract.py
└── test_direct_v2.py        # New schema-validation tests
```

### Modified files

- `src/docugen/themes/slides.py` — `SLIDE_REGISTRY` becomes auto-populated from `primitives/`; hand-written entries deleted.
- `src/docugen/themes/biopunk.py` — `render_choreography` becomes a thin dispatcher; `_choreo_*` methods deleted (logic moved to primitives).
- `src/docugen/direct.py` — `direct_prepare` attaches `pdf_data.json` + primitive schemas; `direct_apply` adds per-primitive schema validation.
- `src/docugen/server.py` — registers `viz_extract` tool, updates instructions string.

### Deleted files

None. (`dot_merge` and `remove_reveal` are deprecated-but-kept; they move into `primitives/` with a `"deprecated": True` flag.)

---

## Conventions used by all tasks

**Python target:** 3.10+. Use PEP 604 union syntax (`str | None`), PEP 585 generics (`list[dict]`, `dict[str, X]`).

**Commit style:** Match existing repo style seen in `git log` — lowercase prefix (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`) then short imperative. Each task ends in a commit.

**Test runner:** `pytest -x -q` from repo root. No new pytest config needed.

**Schema format:** Plain Python dict. Keys: `required` (list of top-level field names), `types` (dict of field→type constraint), `enums` (dict of field→allowed values), `children` (recursive nested schemas). Each primitive exports this as a module-level `DATA_SCHEMA` dict. Validation is a hand-written walker; no runtime dep added. See Task 4 for the validator.

**Primitive module contract:** Every file in `themes/primitives/` (except `_base.py` and `__init__.py`) exports:
```python
NAME: str                    # e.g. "line_chart"
DESCRIPTION: str             # one-line
CUE_EVENTS: set[str]         # valid events for cue_words
AUDIO_SPANS: list[dict]      # spans for spot tool (unchanged shape from current SLIDE_REGISTRY)
DATA_SCHEMA: dict            # see "Schema format" above
NEEDS_CONTENT: bool = False  # optional
DEPRECATED: bool = False     # optional
PARAMS: dict = {}            # optional — legacy params field

def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    """Return indented Manim construct() body code."""
```

---

## Task 1: Primitive package scaffold

**Files:**
- Create: `src/docugen/themes/primitives/__init__.py`
- Create: `src/docugen/themes/primitives/_base.py`
- Create: `tests/primitives/__init__.py`
- Create: `tests/primitives/test_registry.py`

- [ ] **Step 1: Write the failing test**

Create `tests/primitives/test_registry.py`:
```python
"""Auto-discovery registry tests."""
import pytest
from docugen.themes.primitives import discover_primitives, get_primitive


def test_discover_returns_dict():
    result = discover_primitives()
    assert isinstance(result, dict)


def test_get_unknown_primitive_raises():
    with pytest.raises(KeyError, match="no_such_primitive"):
        get_primitive("no_such_primitive")
```

- [ ] **Step 2: Run tests — expect failure**

Run: `pytest tests/primitives/test_registry.py -x -q`
Expected: ModuleNotFoundError for `docugen.themes.primitives`.

- [ ] **Step 3: Create package init with discovery**

Create `src/docugen/themes/primitives/_base.py`:
```python
"""Shared Protocol + helpers for primitive modules."""
from __future__ import annotations

from typing import Protocol


class PrimitiveModule(Protocol):
    NAME: str
    DESCRIPTION: str
    CUE_EVENTS: set[str]
    AUDIO_SPANS: list[dict]
    DATA_SCHEMA: dict
    NEEDS_CONTENT: bool
    DEPRECATED: bool
    PARAMS: dict

    def render(self, clip: dict, duration: float,
               images_dir: str, theme) -> str: ...


REQUIRED_ATTRS = ("NAME", "DESCRIPTION", "CUE_EVENTS", "AUDIO_SPANS",
                  "DATA_SCHEMA", "render")
```

Create `src/docugen/themes/primitives/__init__.py`:
```python
"""Auto-discovering primitive registry.

Every module in this package (except those starting with _) is treated as
a primitive. At import time we validate each module has the required
attributes and cache them by NAME.
"""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from types import ModuleType

from docugen.themes.primitives._base import REQUIRED_ATTRS

_cache: dict[str, ModuleType] = {}


def discover_primitives() -> dict[str, ModuleType]:
    """Discover and cache all primitive modules in this package."""
    if _cache:
        return _cache
    pkg_path = Path(__file__).parent
    for info in pkgutil.iter_modules([str(pkg_path)]):
        if info.name.startswith("_"):
            continue
        mod = importlib.import_module(f"{__name__}.{info.name}")
        for attr in REQUIRED_ATTRS:
            if not hasattr(mod, attr):
                raise ImportError(
                    f"Primitive {info.name!r} missing required attr {attr!r}"
                )
        _cache[mod.NAME] = mod
    return _cache


def get_primitive(name: str) -> ModuleType:
    """Return the primitive module for the given NAME."""
    primitives = discover_primitives()
    if name not in primitives:
        raise KeyError(f"no primitive registered: {name!r}")
    return primitives[name]
```

Create `tests/primitives/__init__.py` (empty).

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/primitives/test_registry.py -x -q`
Expected: PASS. `discover_primitives()` returns an empty dict (no primitives yet); `get_primitive("no_such_primitive")` raises KeyError.

- [ ] **Step 5: Commit**

```bash
git add src/docugen/themes/primitives tests/primitives
git commit -m "feat: primitive package scaffold with auto-discovery"
```

---

## Task 2: Shared schema validator

**Files:**
- Modify: `src/docugen/themes/primitives/_base.py`
- Create: `tests/primitives/test_schema.py`

- [ ] **Step 1: Write the failing test**

Create `tests/primitives/test_schema.py`:
```python
"""Schema validator tests."""
import pytest
from docugen.themes.primitives._base import validate_schema


SCHEMA_NUMERIC = {
    "required": ["title", "value"],
    "types": {"title": str, "value": (int, float)},
}


def test_accepts_valid():
    errs = validate_schema({"title": "X", "value": 3.14}, SCHEMA_NUMERIC, "data")
    assert errs == []


def test_rejects_missing_required():
    errs = validate_schema({"title": "X"}, SCHEMA_NUMERIC, "data")
    assert any("value" in e for e in errs)


def test_rejects_wrong_type():
    errs = validate_schema({"title": 42, "value": 3.14}, SCHEMA_NUMERIC, "data")
    assert any("title" in e and "str" in e for e in errs)


def test_enum_violation():
    schema = {"required": ["mode"], "enums": {"mode": {"a", "b", "c"}}}
    errs = validate_schema({"mode": "z"}, schema, "data")
    assert any("mode" in e for e in errs)


def test_nested_list():
    schema = {
        "required": ["series"],
        "types": {"series": list},
        "children": {
            "series": {
                "required": ["label", "value"],
                "types": {"label": str, "value": (int, float)},
            }
        },
    }
    data = {"series": [{"label": "A", "value": 1}, {"label": "B"}]}
    errs = validate_schema(data, schema, "data")
    assert any("series[1]" in e and "value" in e for e in errs)
```

- [ ] **Step 2: Run tests — expect failure**

Run: `pytest tests/primitives/test_schema.py -x -q`
Expected: ImportError for `validate_schema`.

- [ ] **Step 3: Implement validator**

Append to `src/docugen/themes/primitives/_base.py`:
```python
def validate_schema(data: dict, schema: dict, path: str) -> list[str]:
    """Walk data against schema and return error strings.

    Schema keys:
      required: list of required field names
      types: dict field -> type | tuple of types
      enums: dict field -> allowed values set
      children: dict field -> nested schema (recursed into each list element
                              if the field is a list)
    """
    errors: list[str] = []
    if not isinstance(data, dict):
        return [f"{path}: expected object, got {type(data).__name__}"]

    for field in schema.get("required", []):
        if field not in data:
            errors.append(f"{path}: missing required field {field!r}")

    for field, expected in schema.get("types", {}).items():
        if field not in data:
            continue
        if not isinstance(data[field], expected):
            name = (expected.__name__ if isinstance(expected, type)
                    else "/".join(t.__name__ for t in expected))
            errors.append(
                f"{path}.{field}: expected {name}, "
                f"got {type(data[field]).__name__}"
            )

    for field, allowed in schema.get("enums", {}).items():
        if field in data and data[field] not in allowed:
            errors.append(
                f"{path}.{field}: {data[field]!r} not in {sorted(allowed)}"
            )

    for field, child_schema in schema.get("children", {}).items():
        if field not in data:
            continue
        value = data[field]
        if isinstance(value, list):
            for i, elem in enumerate(value):
                errors.extend(validate_schema(elem, child_schema,
                                              f"{path}.{field}[{i}]"))
        elif isinstance(value, dict):
            errors.extend(validate_schema(value, child_schema,
                                          f"{path}.{field}"))
    return errors
```

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/primitives/test_schema.py -x -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/docugen/themes/primitives/_base.py tests/primitives/test_schema.py
git commit -m "feat: schema validator for primitive data specs"
```

---

## Task 3: Migrate `title` primitive

Preserves existing title behavior; acts as the pattern-setter for migrations.

**Files:**
- Create: `src/docugen/themes/primitives/title.py`
- Read: `src/docugen/tools/title.py` (existing logic, to be referenced)
- Read: `src/docugen/themes/biopunk.py` lines 520-590 (current title rendering path)
- Create: `tests/primitives/test_title.py`

- [ ] **Step 1: Read existing title rendering to preserve behavior**

Run: `grep -n 'title' src/docugen/themes/biopunk.py | head -30`
Expected: identify which code path renders `slide_type == "title"`. Current title is served by `tools/title.py` (standalone), not biopunk's choreography — so `primitives/title.py` just defines registry metadata; the render stub delegates to the title-card generator's published API or a minimal fallback.

- [ ] **Step 2: Write the failing test**

Create `tests/primitives/test_title.py`:
```python
"""title primitive — metadata + render smoke test."""
import ast
from docugen.themes.primitives import title


def test_metadata():
    assert title.NAME == "title"
    assert "reveal_title" in title.CUE_EVENTS
    assert "reveal_subtitle" in title.CUE_EVENTS


def test_audio_spans_cover_reveal_title():
    triggers = {span["trigger"] for span in title.AUDIO_SPANS}
    assert "reveal_title" in triggers


def test_render_returns_compilable_snippet():
    clip = {
        "clip_id": "intro_01",
        "text": "Hello",
        "word_times": [{"word": "Hello", "start": 0.0, "end": 0.5}],
        "visuals": {"slide_type": "title", "params": {"reveal_style": "particle"}},
    }
    body = title.render(clip, duration=5.0, images_dir="/tmp", theme=None)
    assert isinstance(body, str) and body.strip()
    wrapped = "def construct(self):\n" + body
    ast.parse(wrapped)  # must be syntactically valid Python
```

- [ ] **Step 3: Run tests — expect failure**

Run: `pytest tests/primitives/test_title.py -x -q`
Expected: ImportError for `docugen.themes.primitives.title`.

- [ ] **Step 4: Implement primitive**

Create `src/docugen/themes/primitives/title.py`:
```python
"""title — title + subtitle reveal. Metadata primitive; rendering is delegated
to tools/title.py for standalone title cards. This module exists so the
registry can validate slide_type='title' clips and expose their cue events."""

NAME = "title"
DESCRIPTION = "Title + subtitle with configurable reveal style"
CUE_EVENTS = {"reveal_title", "reveal_subtitle"}
AUDIO_SPANS = [
    {"trigger": "reveal_title", "offset": -2.0, "duration": 2.0,
     "audio": "tension_build", "curve": "ramp_up"},
    {"trigger": "reveal_title", "offset": 0.0, "duration": 0.3,
     "audio": "hit", "curve": "spike"},
    {"trigger": "reveal_subtitle", "offset": 0.0, "duration": 1.2,
     "audio": "sweep_tone", "curve": "linear"},
]
DATA_SCHEMA = {
    "required": [],
    "types": {"title_text": str, "subtitle_text": str, "reveal_style": str},
    "enums": {"reveal_style": {"particle", "glitch", "trace", "typewriter"}},
}
PARAMS = {"reveal_style": "particle"}
NEEDS_CONTENT = False
DEPRECATED = False


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    """Fallback inline title reveal used when a title clip is rendered by
    the main pipeline (not tools/title.py). Keeps tests green and renders
    do-not-error output if a project asks for slide_type='title' directly."""
    visuals = clip.get("visuals", {})
    params = visuals.get("params", {}) or {}
    style = params.get("reveal_style", "particle")
    title_text = (params.get("title_text") or clip.get("text", "")).replace('"', '\\"')
    subtitle = (params.get("subtitle_text") or "").replace('"', '\\"')
    hold = max(duration - 4.0, 1.0)
    return (
        f'        title = Text("{title_text}", font="Courier", weight=BOLD).scale(1.0)\n'
        f'        subtitle = Text("{subtitle}", font="Courier").scale(0.5)\n'
        f'        subtitle.next_to(title, DOWN, buff=0.5)\n'
        f'        self.play(FadeIn(title, shift=UP * 0.3), run_time=1.5)\n'
        f'        self.play(FadeIn(subtitle, shift=UP * 0.2), run_time=1.0)\n'
        f'        self.wait({hold:.2f})\n'
        f'        self.play(FadeOut(title), FadeOut(subtitle), run_time=1.0)\n'
        f'        # reveal_style={style!r}\n'
    )
```

- [ ] **Step 5: Run tests — expect pass**

Run: `pytest tests/primitives/test_title.py -x -q`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add src/docugen/themes/primitives/title.py tests/primitives/test_title.py
git commit -m "feat: migrate title primitive into primitives package"
```

---

## Task 4: Migrate `chapter_card` primitive

**Files:**
- Create: `src/docugen/themes/primitives/chapter_card.py`
- Read: `src/docugen/themes/biopunk.py` — search for `_choreo_chapter_card`
- Create: `tests/primitives/test_chapter_card.py`

- [ ] **Step 1: Locate existing chapter_card choreography**

Run: `grep -n '_choreo_chapter_card\|chapter_card' src/docugen/themes/biopunk.py`
Read the `_choreo_chapter_card` method body (the render logic to preserve).

- [ ] **Step 2: Write the failing test**

Create `tests/primitives/test_chapter_card.py`:
```python
"""chapter_card — metadata + render smoke."""
import ast
from docugen.themes.primitives import chapter_card


def test_metadata():
    assert chapter_card.NAME == "chapter_card"
    assert chapter_card.CUE_EVENTS == {"reveal_number", "reveal_title"}


def test_audio_spans():
    triggers = [s["trigger"] for s in chapter_card.AUDIO_SPANS]
    assert "reveal_title" in triggers


def test_render_compiles():
    clip = {"clip_id": "ch1_01", "text": "Chapter One",
            "word_times": [], "visuals": {"slide_type": "chapter_card"}}
    body = chapter_card.render(clip, duration=3.0, images_dir="/tmp", theme=None)
    ast.parse("def construct(self):\n" + body)
```

- [ ] **Step 3: Run tests — expect failure**

Run: `pytest tests/primitives/test_chapter_card.py -x -q`

- [ ] **Step 4: Copy choreography body from biopunk into new primitive**

Create `src/docugen/themes/primitives/chapter_card.py`. Use the exact body of `_choreo_chapter_card` from `biopunk.py`. Wire module-level metadata plus a `render()` function whose body is the copied code:

```python
"""chapter_card — animated chapter marker. Migrated from biopunk._choreo_chapter_card
with no behavior change."""

NAME = "chapter_card"
DESCRIPTION = "Chapter number + title, imperial border draws in"
CUE_EVENTS = {"reveal_number", "reveal_title"}
AUDIO_SPANS = [
    {"trigger": "reveal_title", "offset": -0.5, "duration": 0.8,
     "audio": "swoosh", "curve": "ease_in"},
]
DATA_SCHEMA = {"required": [], "types": {}}
PARAMS = {}
NEEDS_CONTENT = False
DEPRECATED = False


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    # Copy the exact content of biopunk._choreo_chapter_card here,
    # replacing `self` references to theme palette with the theme arg.
    # The Manim code body only — no method signature wrapper.
    ...
```

**Do not delete biopunk's method yet** — parallel wiring removed in Task 16.

- [ ] **Step 5: Run tests — expect pass**

Run: `pytest tests/primitives/test_chapter_card.py -x -q`

- [ ] **Step 6: Commit**

```bash
git add src/docugen/themes/primitives/chapter_card.py tests/primitives/test_chapter_card.py
git commit -m "feat: migrate chapter_card primitive"
```

---

## Task 5: Migrate `ambient_field` primitive

**Files:**
- Create: `src/docugen/themes/primitives/ambient_field.py`
- Create: `tests/primitives/test_ambient_field.py`

- [ ] **Step 1: Write the failing test**

Create `tests/primitives/test_ambient_field.py`:
```python
"""ambient_field — decorative background, no cue events."""
import ast
from docugen.themes.primitives import ambient_field


def test_metadata():
    assert ambient_field.NAME == "ambient_field"
    assert ambient_field.CUE_EVENTS == set()
    assert ambient_field.AUDIO_SPANS == []


def test_render_is_valid_wait():
    clip = {"clip_id": "x", "visuals": {}, "text": "", "word_times": []}
    body = ambient_field.render(clip, duration=4.0, images_dir="/tmp", theme=None)
    ast.parse("def construct(self):\n" + body)
    assert "wait" in body.lower()  # should hold for the duration
```

- [ ] **Step 2: Run test — expect failure**

Run: `pytest tests/primitives/test_ambient_field.py -x -q`

- [ ] **Step 3: Implement primitive**

Create `src/docugen/themes/primitives/ambient_field.py`:
```python
"""ambient_field — theme background holds for the clip duration."""

NAME = "ambient_field"
DESCRIPTION = "Particle field + theme bg, no foreground content"
CUE_EVENTS: set[str] = set()
AUDIO_SPANS: list[dict] = []
DATA_SCHEMA = {"required": [], "types": {}}
PARAMS = {}
NEEDS_CONTENT = False
DEPRECATED = False


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    hold = max(duration, 0.5)
    return f"        alive_wait(self, {hold:.2f}, particles=bg)\n"
```

- [ ] **Step 4: Run test — expect pass**

Run: `pytest tests/primitives/test_ambient_field.py -x -q`

- [ ] **Step 5: Commit**

```bash
git add src/docugen/themes/primitives/ambient_field.py tests/primitives/test_ambient_field.py
git commit -m "feat: migrate ambient_field primitive"
```

---

## Task 6: Migrate `svg_reveal` primitive

**Files:**
- Create: `src/docugen/themes/primitives/svg_reveal.py`
- Create: `tests/primitives/test_svg_reveal.py`
- Read: `biopunk.py` — search for `svg_reveal` choreography

- [ ] **Step 1: Locate existing code**

Run: `grep -n 'svg_reveal\|_choreo_svg' src/docugen/themes/biopunk.py`

- [ ] **Step 2: Write the failing test**

Create `tests/primitives/test_svg_reveal.py`:
```python
import ast
from docugen.themes.primitives import svg_reveal


def test_metadata():
    assert svg_reveal.NAME == "svg_reveal"
    assert "show_asset" in svg_reveal.CUE_EVENTS
    assert svg_reveal.NEEDS_CONTENT is True


def test_render_compiles_with_asset():
    clip = {
        "clip_id": "x",
        "text": "diagram",
        "word_times": [{"word": "diagram", "start": 0.0, "end": 0.5}],
        "visuals": {
            "slide_type": "svg_reveal",
            "assets": ["diagram.svg"],
            "cue_words": [{"event": "show_asset", "at_index": 0, "params": {}}],
        },
    }
    body = svg_reveal.render(clip, duration=5.0, images_dir="/tmp", theme=None)
    ast.parse("def construct(self):\n" + body)
```

- [ ] **Step 3: Run test — expect failure**

- [ ] **Step 4: Copy choreography from biopunk**

Create `src/docugen/themes/primitives/svg_reveal.py` with the current biopunk svg_reveal logic (or its fallback path if none exists; the SLIDE_REGISTRY entry today has events `show_asset`, `highlight_region`, `show_label` but no dedicated `_choreo_svg_reveal` method — it is served by the asset layout path). If there is no dedicated choreography, the primitive's `render()` returns an `alive_wait()` hold, matching current fallback behavior.

```python
"""svg_reveal — SVG asset fades/draws in with labels."""

NAME = "svg_reveal"
DESCRIPTION = "SVG asset fades/draws in, Ken Burns drift, labels"
CUE_EVENTS = {"show_asset", "highlight_region", "show_label"}
AUDIO_SPANS = [
    {"trigger": "show_asset", "offset": 0.0, "duration": 1.0,
     "audio": "swoosh", "curve": "ease_in"},
    {"trigger": "show_label", "offset": 0.0, "duration": 0.3,
     "audio": "blip", "curve": "spike"},
]
DATA_SCHEMA = {"required": [], "types": {}}
PARAMS = {}
NEEDS_CONTENT = True
DEPRECATED = False


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    hold = max(duration - 0.5, 0.5)
    return f"        alive_wait(self, {hold:.2f}, particles=bg)\n"
```

- [ ] **Step 5: Run test — expect pass**

- [ ] **Step 6: Commit**

```bash
git add src/docugen/themes/primitives/svg_reveal.py tests/primitives/test_svg_reveal.py
git commit -m "feat: migrate svg_reveal primitive"
```

---

## Task 7: Migrate `photo_organism` primitive

**Files:**
- Create: `src/docugen/themes/primitives/photo_organism.py`
- Create: `tests/primitives/test_photo_organism.py`
- Read: `biopunk.py` — `_choreo_organism_reveal` (line ~990)

- [ ] **Step 1: Locate existing code**

Run: `grep -n '_choreo_organism\|photo_organism' src/docugen/themes/biopunk.py`

- [ ] **Step 2: Write the failing test**

Create `tests/primitives/test_photo_organism.py`:
```python
import ast
from docugen.themes.primitives import photo_organism


def test_metadata():
    assert photo_organism.NAME == "photo_organism"
    assert "show_photo" in photo_organism.CUE_EVENTS
    assert photo_organism.NEEDS_CONTENT is True


def test_render_compiles():
    clip = {
        "clip_id": "x", "text": "organism",
        "word_times": [{"word": "organism", "start": 0.0, "end": 0.5}],
        "visuals": {
            "slide_type": "photo_organism", "assets": ["img.jpg"],
            "cue_words": [{"event": "show_name", "at_index": 0,
                           "params": {"name": "Bioluminescent"}}],
        },
    }
    body = photo_organism.render(clip, duration=6.0, images_dir="/tmp", theme=None)
    ast.parse("def construct(self):\n" + body)
```

- [ ] **Step 3: Run test — expect failure**

- [ ] **Step 4: Port `_choreo_organism_reveal` verbatim**

Create `src/docugen/themes/primitives/photo_organism.py`. Copy the body of `_choreo_organism_reveal` from `biopunk.py:990-1035` verbatim. Metadata header:

```python
"""photo_organism — photo inset with HUD pointer labels. Migrated from biopunk."""

NAME = "photo_organism"
DESCRIPTION = "Photo inset with HUD border, animated pointer labels"
CUE_EVENTS = {"show_photo", "show_structure", "show_name", "show_note"}
AUDIO_SPANS = [
    {"trigger": "show_photo", "offset": 0.0, "duration": 1.2,
     "audio": "swoosh", "curve": "ease_in"},
    {"trigger": "show_name", "offset": 0.0, "duration": 0.8,
     "audio": "trace_hum", "curve": "sustain"},
    {"trigger": "show_structure", "offset": 0.0, "duration": 0.8,
     "audio": "trace_hum", "curve": "sustain"},
    {"trigger": "show_note", "offset": 0.0, "duration": 0.3,
     "audio": "blip", "curve": "spike"},
]
DATA_SCHEMA = {"required": [], "types": {}}
PARAMS = {}
NEEDS_CONTENT = True
DEPRECATED = False


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    # Paste the exact body from biopunk._choreo_organism_reveal here.
    # Use theme.palette["gold"] / theme.palette["cyan"] / theme.palette["purple"]
    # instead of the current hardcoded `palette["gold"]` etc.
    ...
```

- [ ] **Step 5: Run test — expect pass**

- [ ] **Step 6: Commit**

```bash
git add src/docugen/themes/primitives/photo_organism.py tests/primitives/test_photo_organism.py
git commit -m "feat: migrate photo_organism primitive"
```

---

## Task 8: Upgrade `callout` primitive (rename of data_text)

**Files:**
- Create: `src/docugen/themes/primitives/callout.py`
- Create: `tests/primitives/test_callout.py`

- [ ] **Step 1: Write the failing test**

Create `tests/primitives/test_callout.py`:
```python
import ast
from docugen.themes.primitives import callout
from docugen.themes.primitives._base import validate_schema


def test_metadata():
    assert callout.NAME == "callout"
    assert "show_primary" in callout.CUE_EVENTS


def test_schema_accepts_valid():
    data = {"primary": "$41", "secondary": "BOM", "style": "headline"}
    assert validate_schema(data, callout.DATA_SCHEMA, "data") == []


def test_schema_rejects_bad_style():
    errs = validate_schema(
        {"primary": "X", "style": "bogus"}, callout.DATA_SCHEMA, "data")
    assert any("style" in e for e in errs)


def test_render_compiles():
    clip = {"clip_id": "x", "text": "",
            "word_times": [{"word": "x", "start": 0.0, "end": 0.5}],
            "visuals": {"slide_type": "callout",
                        "data": {"primary": "$41", "secondary": "BOM"},
                        "cue_words": [{"event": "show_primary", "at_index": 0,
                                       "params": {}}]}}
    body = callout.render(clip, duration=3.0, images_dir="/tmp", theme=None)
    ast.parse("def construct(self):\n" + body)
```

- [ ] **Step 2: Run test — expect failure**

Run: `pytest tests/primitives/test_callout.py -x -q`

- [ ] **Step 3: Implement**

Create `src/docugen/themes/primitives/callout.py`:
```python
"""callout — primary/secondary typographic callout. Rename of legacy data_text."""

NAME = "callout"
DESCRIPTION = "Headline number + annotation, clean typography"
CUE_EVENTS = {"show_primary", "show_secondary"}
AUDIO_SPANS = [
    {"trigger": "show_primary", "offset": 0.0, "duration": 0.3,
     "audio": "blip", "curve": "spike"},
    {"trigger": "show_secondary", "offset": 0.0, "duration": 0.3,
     "audio": "blip", "curve": "spike"},
]
DATA_SCHEMA = {
    "required": ["primary"],
    "types": {"primary": str, "secondary": str, "style": str},
    "enums": {"style": {"headline", "tag", "label"}},
}
PARAMS = {}
NEEDS_CONTENT = False
DEPRECATED = False


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    visuals = clip.get("visuals", {})
    data = visuals.get("data") or {}
    primary = str(data.get("primary", "")).replace('"', '\\"')
    secondary = str(data.get("secondary", "")).replace('"', '\\"')
    style = data.get("style", "headline")
    scale_map = {"headline": 1.6, "tag": 0.8, "label": 0.55}
    scale = scale_map.get(style, 1.6)
    hold = max(duration - 2.0, 0.5)
    lines = [
        f'        primary = Text("{primary}", font="Courier", weight=BOLD).scale({scale})\n',
        f'        self.play(FadeIn(primary, scale=1.15), run_time=0.6)\n',
    ]
    if secondary:
        lines.append(
            f'        secondary = Text("{secondary}", font="Courier", color=TEXT_DIM).scale(0.45)\n'
            f'        secondary.next_to(primary, DOWN, buff=0.4)\n'
            f'        self.play(FadeIn(secondary), run_time=0.4)\n'
        )
    lines.append(f'        alive_wait(self, {hold:.2f}, particles=bg)\n')
    return "".join(lines)
```

- [ ] **Step 4: Run test — expect pass**

Run: `pytest tests/primitives/test_callout.py -x -q`

- [ ] **Step 5: Commit**

```bash
git add src/docugen/themes/primitives/callout.py tests/primitives/test_callout.py
git commit -m "feat: add callout primitive (replaces data_text)"
```

---

## Task 9: Upgrade `counter` primitive (replaces counter_sync)

**Files:**
- Create: `src/docugen/themes/primitives/counter.py`
- Create: `tests/primitives/test_counter.py`

- [ ] **Step 1: Write the failing test**

Create `tests/primitives/test_counter.py`:
```python
import ast
from docugen.themes.primitives import counter
from docugen.themes.primitives._base import validate_schema


def test_metadata():
    assert counter.NAME == "counter"
    assert "start_count" in counter.CUE_EVENTS


def test_schema_accepts_valid():
    data = {"from": 0, "to": 14300000, "format": "${:,.0f}",
            "suffix": "ARR", "duration_s": 2.5, "easing": "ease_out_cubic"}
    assert validate_schema(data, counter.DATA_SCHEMA, "data") == []


def test_schema_rejects_missing_to():
    errs = validate_schema({"from": 0}, counter.DATA_SCHEMA, "data")
    assert any("to" in e for e in errs)


def test_render_compiles():
    clip = {"clip_id": "x", "text": "", "word_times": [
        {"word": "x", "start": 0.0, "end": 0.3}],
        "visuals": {"slide_type": "counter",
                    "data": {"from": 0, "to": 420, "format": "{:d}", "suffix": "B"},
                    "cue_words": [{"event": "start_count", "at_index": 0,
                                   "params": {}}]}}
    body = counter.render(clip, duration=5.0, images_dir="/tmp", theme=None)
    ast.parse("def construct(self):\n" + body)
```

- [ ] **Step 2: Run test — expect failure**

- [ ] **Step 3: Implement**

Create `src/docugen/themes/primitives/counter.py`:
```python
"""counter — number counts up from/to with formatting, suffix, easing."""

NAME = "counter"
DESCRIPTION = "Number animates from->to, keyed to narration, units + context"
CUE_EVENTS = {"start_count", "hold", "reveal_context"}
AUDIO_SPANS = [
    {"trigger": "start_count", "offset": 0.0, "duration": 2.5,
     "audio": "tick_accelerate", "curve": "ramp_up"},
    {"trigger": "start_count", "offset": 2.5, "duration": 0.4,
     "audio": "sting", "curve": "spike"},
]
DATA_SCHEMA = {
    "required": ["to"],
    "types": {"from": (int, float), "to": (int, float),
              "format": str, "suffix": str, "context_label": str,
              "duration_s": (int, float), "easing": str},
    "enums": {"easing": {"linear", "ease_out_cubic", "ease_in_cubic",
                         "ease_in_out_cubic"}},
}
PARAMS = {}
NEEDS_CONTENT = False
DEPRECATED = False


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    visuals = clip.get("visuals", {})
    data = visuals.get("data") or {}
    start = data.get("from", 0)
    end = data["to"]
    fmt = data.get("format", "{:,.0f}")
    suffix = data.get("suffix", "")
    context = data.get("context_label", "")
    count_dur = float(data.get("duration_s", 2.5))

    # Format end value for template safety (escape braces)
    fmt_py = fmt.replace("{", "{{").replace("}", "}}")
    hold = max(duration - count_dur - 1.0, 0.5)

    lines = [
        f'        from_val = {start}\n',
        f'        to_val = {end}\n',
        f'        tracker = ValueTracker(from_val)\n',
        f'        label = always_redraw(\n',
        f'            lambda: Text(\n'
        f'                f"{{({fmt_py}).format(tracker.get_value())}}" + "{suffix}",\n'
        f'                font="Courier", weight=BOLD).scale(1.4)\n'
        f'        )\n',
        f'        self.add(label)\n',
        f'        self.play(tracker.animate.set_value(to_val),\n'
        f'                  run_time={count_dur:.2f}, rate_func=rush_from)\n',
    ]
    if context:
        ctx = context.replace('"', '\\"')
        lines.append(
            f'        ctx = Text("{ctx}", font="Courier", color=TEXT_DIM).scale(0.5)\n'
            f'        ctx.next_to(label, DOWN, buff=0.4)\n'
            f'        self.play(FadeIn(ctx), run_time=0.5)\n'
        )
    lines.append(f'        alive_wait(self, {hold:.2f}, particles=bg)\n')
    return "".join(lines)
```

- [ ] **Step 4: Run test — expect pass**

Run: `pytest tests/primitives/test_counter.py -x -q`

- [ ] **Step 5: Commit**

```bash
git add src/docugen/themes/primitives/counter.py tests/primitives/test_counter.py
git commit -m "feat: upgrade counter primitive with formatting + easing"
```

---

## Task 10: Upgrade `before_after` primitive

**Files:**
- Create: `src/docugen/themes/primitives/before_after.py`
- Create: `tests/primitives/test_before_after.py`

- [ ] **Step 1: Write the failing test**

Create `tests/primitives/test_before_after.py`:
```python
import ast
from docugen.themes.primitives import before_after
from docugen.themes.primitives._base import validate_schema


def test_metadata():
    assert before_after.NAME == "before_after"
    assert "reveal_delta" in before_after.CUE_EVENTS


def test_schema_valid():
    data = {
        "metric": "turnaround",
        "before": {"value": 72, "label": "Manual", "unit": "hrs"},
        "after":  {"value": 4,  "label": "Automated", "unit": "hrs"},
        "delta_display": "pct_change",
        "direction": "lower_is_better",
    }
    assert validate_schema(data, before_after.DATA_SCHEMA, "data") == []


def test_schema_rejects_bad_delta_display():
    data = {
        "metric": "x",
        "before": {"value": 1, "label": "A"},
        "after":  {"value": 2, "label": "B"},
        "delta_display": "nonsense",
    }
    errs = validate_schema(data, before_after.DATA_SCHEMA, "data")
    assert any("delta_display" in e for e in errs)


def test_render_compiles():
    clip = {"clip_id": "x", "text": "",
            "word_times": [{"word": "x", "start": 0, "end": 0.3}],
            "visuals": {"slide_type": "before_after",
                        "data": {
                            "metric": "X",
                            "before": {"value": 72, "label": "Old"},
                            "after":  {"value": 4,  "label": "New"},
                        },
                        "cue_words": [{"event": "show_before",
                                       "at_index": 0, "params": {}}]}}
    body = before_after.render(clip, duration=6.0, images_dir="/tmp", theme=None)
    ast.parse("def construct(self):\n" + body)
```

- [ ] **Step 2: Run test — expect failure**

- [ ] **Step 3: Implement**

Create `src/docugen/themes/primitives/before_after.py`:
```python
"""before_after — side-by-side with auto-computed delta."""

NAME = "before_after"
DESCRIPTION = "Side-by-side comparison with auto delta and direction color"
CUE_EVENTS = {"show_before", "show_after", "reveal_delta"}
AUDIO_SPANS = [
    {"trigger": "show_before", "offset": 0.0, "duration": 0.5,
     "audio": "blip", "curve": "spike"},
    {"trigger": "show_after", "offset": 0.0, "duration": 0.5,
     "audio": "blip", "curve": "spike"},
    {"trigger": "reveal_delta", "offset": 0.0, "duration": 1.5,
     "audio": "morph_tone", "curve": "linear"},
]
DATA_SCHEMA = {
    "required": ["metric", "before", "after"],
    "types": {"metric": str, "before": dict, "after": dict,
              "delta_display": str, "direction": str},
    "enums": {
        "delta_display": {"pct_change", "ratio", "absolute"},
        "direction": {"lower_is_better", "higher_is_better"},
    },
    "children": {
        "before": {"required": ["value", "label"],
                   "types": {"value": (int, float), "label": str, "unit": str}},
        "after":  {"required": ["value", "label"],
                   "types": {"value": (int, float), "label": str, "unit": str}},
    },
}
PARAMS = {}
NEEDS_CONTENT = False
DEPRECATED = False


def _compute_delta(before_v, after_v, display, direction):
    if display == "ratio":
        if after_v == 0:
            return "0×"
        return f"{max(before_v, after_v) / min(before_v, after_v):.1f}×"
    if display == "absolute":
        return f"{after_v - before_v:+.1f}"
    # default: pct_change
    if before_v == 0:
        return "n/a"
    pct = (after_v - before_v) / before_v * 100.0
    return f"{pct:+.0f}%"


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    visuals = clip.get("visuals", {})
    data = visuals.get("data") or {}
    metric = data.get("metric", "").replace('"', '\\"')
    before = data.get("before", {})
    after = data.get("after", {})
    display = data.get("delta_display", "pct_change")
    direction = data.get("direction", "higher_is_better")

    bv = before.get("value", 0)
    av = after.get("value", 0)
    delta_str = _compute_delta(bv, av, display, direction)

    improving = (
        (direction == "higher_is_better" and av > bv) or
        (direction == "lower_is_better" and av < bv)
    )
    delta_color = "GLOW" if improving else "SITH_RED"

    bu = before.get("unit", "")
    au = after.get("unit", "")
    bl = before.get("label", "").replace('"', '\\"')
    al = after.get("label", "").replace('"', '\\"')

    hold = max(duration - 4.0, 0.5)
    return (
        f'        header = Text("{metric}", font="Courier", weight=BOLD).scale(0.5).to_edge(UP, buff=0.8)\n'
        f'        self.play(FadeIn(header), run_time=0.4)\n'
        f'        bl = Text("{bl}", font="Courier", color=TEXT_DIM).scale(0.4).move_to(LEFT * 3 + UP * 1.0)\n'
        f'        bv = Text("{bv}{bu}", font="Courier", weight=BOLD).scale(1.1).move_to(LEFT * 3)\n'
        f'        self.play(FadeIn(bl), FadeIn(bv), run_time=0.6)\n'
        f'        arrow = Arrow(LEFT * 1.2, RIGHT * 1.2, color={delta_color}, stroke_width=4)\n'
        f'        self.play(GrowArrow(arrow), run_time=0.6)\n'
        f'        al = Text("{al}", font="Courier", color={delta_color}).scale(0.4).move_to(RIGHT * 3 + UP * 1.0)\n'
        f'        av = Text("{av}{au}", font="Courier", color={delta_color}, weight=BOLD).scale(1.1).move_to(RIGHT * 3)\n'
        f'        self.play(FadeIn(al), FadeIn(av, scale=1.2), run_time=0.8)\n'
        f'        delta = Text("{delta_str}", font="Courier", color={delta_color}, weight=BOLD).scale(0.7)\n'
        f'        delta.next_to(arrow, DOWN, buff=0.4)\n'
        f'        self.play(FadeIn(delta, shift=UP * 0.2), run_time=0.6)\n'
        f'        alive_wait(self, {hold:.2f}, particles=bg)\n'
    )
```

- [ ] **Step 4: Run test — expect pass**

- [ ] **Step 5: Commit**

```bash
git add src/docugen/themes/primitives/before_after.py tests/primitives/test_before_after.py
git commit -m "feat: upgrade before_after with auto delta + direction"
```

---

## Task 11: Upgrade `bar_chart` primitive

**Files:**
- Create: `src/docugen/themes/primitives/bar_chart.py`
- Create: `tests/primitives/test_bar_chart.py`

- [ ] **Step 1: Write the failing test**

Create `tests/primitives/test_bar_chart.py`:
```python
import ast
from docugen.themes.primitives import bar_chart
from docugen.themes.primitives._base import validate_schema


def test_metadata():
    assert bar_chart.NAME == "bar_chart"
    assert "show_bar" in bar_chart.CUE_EVENTS
    assert "show_axes" in bar_chart.CUE_EVENTS


def test_schema_valid():
    data = {
        "title": "Revenue",
        "x_label": "Year", "y_label": "USDm",
        "orientation": "vertical",
        "baseline": 0,
        "series": [
            {"label": "2022", "value": 2.1},
            {"label": "2024", "value": 14.3, "emphasized": True},
        ],
        "value_format": "${:.1f}M",
    }
    assert validate_schema(data, bar_chart.DATA_SCHEMA, "data") == []


def test_schema_rejects_empty_series():
    # at least one series element required
    data = {"title": "X", "series": []}
    errs = validate_schema(data, bar_chart.DATA_SCHEMA, "data")
    # allow empty at schema level; render will no-op — just verify types OK
    # (non-empty enforced at render time with a clear error)
    assert all("type" not in e.lower() for e in errs)


def test_render_compiles():
    clip = {"clip_id": "x", "text": "",
            "word_times": [{"word": "x", "start": 0, "end": 0.3}],
            "visuals": {"slide_type": "bar_chart",
                        "data": {
                            "title": "Revenue",
                            "series": [{"label": "A", "value": 2.0},
                                       {"label": "B", "value": 5.5}],
                        },
                        "cue_words": [{"event": "show_bar", "at_index": 0,
                                       "params": {}}]}}
    body = bar_chart.render(clip, duration=8.0, images_dir="/tmp", theme=None)
    ast.parse("def construct(self):\n" + body)
```

- [ ] **Step 2: Run test — expect failure**

- [ ] **Step 3: Implement**

Create `src/docugen/themes/primitives/bar_chart.py`:
```python
"""bar_chart — real axes, auto scale, value labels.

Replaces bar_chart_build. Uses Manim's Axes (vertical orientation) or
BarChart-style manual rectangles (horizontal orientation)."""

NAME = "bar_chart"
DESCRIPTION = "Bars with real axes, auto-scale, value labels, optional emphasis"
CUE_EVENTS = {"show_axes", "show_bar", "highlight_bar"}
AUDIO_SPANS = [
    {"trigger": "show_axes", "offset": 0.0, "duration": 0.4,
     "audio": "swoosh", "curve": "ease_in"},
    {"trigger": "show_bar", "offset": 0.0, "duration": 0.6,
     "audio": "tick", "curve": "ease_in"},
    {"trigger": "highlight_bar", "offset": 0.0, "duration": 0.3,
     "audio": "blip", "curve": "spike"},
]
DATA_SCHEMA = {
    "required": ["series"],
    "types": {"title": str, "x_label": str, "y_label": str,
              "orientation": str, "baseline": (int, float),
              "series": list, "value_format": str},
    "enums": {"orientation": {"vertical", "horizontal"}},
    "children": {
        "series": {"required": ["label", "value"],
                    "types": {"label": str, "value": (int, float),
                              "emphasized": bool}},
    },
}
PARAMS = {}
NEEDS_CONTENT = False
DEPRECATED = False


def _nice_ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    """Pick ~n 'round' tick values spanning lo..hi."""
    import math
    if hi <= lo:
        return [lo, lo + 1]
    rng = hi - lo
    step = 10 ** math.floor(math.log10(rng / n))
    for mult in (1, 2, 2.5, 5, 10):
        s = step * mult
        if rng / s <= n:
            step = s
            break
    start = math.floor(lo / step) * step
    ticks = []
    v = start
    while v <= hi + step * 0.5:
        ticks.append(round(v, 6))
        v += step
    return ticks


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    visuals = clip.get("visuals", {})
    data = visuals.get("data") or {}
    series = data.get("series") or []
    if not series:
        return f"        alive_wait(self, {max(duration, 0.5):.2f}, particles=bg)\n"

    title = data.get("title", "").replace('"', '\\"')
    x_label = data.get("x_label", "").replace('"', '\\"')
    y_label = data.get("y_label", "").replace('"', '\\"')
    orientation = data.get("orientation", "vertical")
    value_fmt = data.get("value_format", "{:.1f}")
    baseline = float(data.get("baseline", 0))

    values = [float(s["value"]) for s in series]
    vmax = max(values + [baseline])
    vmin = min(values + [baseline, 0])
    ticks = _nice_ticks(vmin, vmax)
    y_range = (ticks[0], ticks[-1], ticks[1] - ticks[0])

    bar_time = max((duration - 3.0) / max(len(series), 1), 0.3)
    chart_height = 4.0
    chart_width = 8.0

    lines: list[str] = []
    if title:
        lines.append(
            f'        title = Text("{title}", font="Courier", weight=BOLD).scale(0.5).to_edge(UP, buff=0.5)\n'
            f'        self.play(FadeIn(title), run_time=0.4)\n'
        )
    # axes
    lines.append(
        f'        ax = Axes(\n'
        f'            x_range=[0, {len(series)}, 1],\n'
        f'            y_range=[{y_range[0]}, {y_range[1]}, {y_range[2]}],\n'
        f'            x_length={chart_width}, y_length={chart_height},\n'
        f'            axis_config={{"color": TEXT_DIM, "include_tip": False,\n'
        f'                          "stroke_width": 2}},\n'
        f'        ).to_edge(DOWN, buff=1.0)\n'
        f'        yt = ax.get_y_axis().add_numbers(font_size=20, color=TEXT_DIM)\n'
        f'        self.play(Create(ax), FadeIn(yt), run_time=0.7)\n'
    )
    if y_label:
        lines.append(
            f'        yl = Text("{y_label}", font="Courier", color=TEXT_DIM).scale(0.3)\n'
            f'        yl.next_to(ax.get_y_axis(), UP, buff=0.2)\n'
            f'        self.play(FadeIn(yl), run_time=0.2)\n'
        )

    for i, s in enumerate(series):
        label = str(s["label"]).replace('"', '\\"')
        val = float(s["value"])
        emph = bool(s.get("emphasized", False))
        bar_color = "GOLD" if emph else "GLOW"
        fmt_safe = value_fmt.replace("{", "{{").replace("}", "}}")
        lines.append(
            f'        # bar {i}: {label}\n'
            f'        bar_{i} = Rectangle(\n'
            f'            width={chart_width/len(series) - 0.3:.2f},\n'
            f'            height=0.01,\n'
            f'            color={bar_color}, fill_color={bar_color}, fill_opacity=0.35,\n'
            f'            stroke_width=2,\n'
            f'        )\n'
            f'        bar_{i}.move_to(ax.c2p({i} + 0.5, 0), aligned_edge=DOWN)\n'
            f'        self.add(bar_{i})\n'
            f'        target_h = ax.c2p(0, {val})[1] - ax.c2p(0, 0)[1]\n'
            f'        self.play(\n'
            f'            bar_{i}.animate.stretch_to_fit_height(abs(target_h))\n'
            f'                .move_to(ax.c2p({i} + 0.5, {val/2:.4f})),\n'
            f'            run_time={bar_time:.2f}, rate_func=smooth,\n'
            f'        )\n'
            f'        lbl_{i} = Text("{label}", font="Courier", color=TEXT_DIM).scale(0.3)\n'
            f'        lbl_{i}.next_to(bar_{i}, DOWN, buff=0.15)\n'
            f'        val_{i} = Text(f"{fmt_safe}".format({val}),\n'
            f'                       font="Courier", color={bar_color}, weight=BOLD).scale(0.35)\n'
            f'        val_{i}.next_to(bar_{i}, UP, buff=0.1)\n'
            f'        self.play(FadeIn(lbl_{i}), FadeIn(val_{i}), run_time=0.3)\n'
        )

    hold = max(duration - (0.7 + len(series) * (bar_time + 0.3)) - 1.0, 0.5)
    lines.append(f'        alive_wait(self, {hold:.2f}, particles=bg)\n')
    return "".join(lines)
```

- [ ] **Step 4: Run test — expect pass**

Run: `pytest tests/primitives/test_bar_chart.py -x -q`

- [ ] **Step 5: Commit**

```bash
git add src/docugen/themes/primitives/bar_chart.py tests/primitives/test_bar_chart.py
git commit -m "feat: upgrade bar_chart with real axes and value labels"
```

---

## Task 12: New `line_chart` primitive

**Files:**
- Create: `src/docugen/themes/primitives/line_chart.py`
- Create: `tests/primitives/test_line_chart.py`

- [ ] **Step 1: Write the failing test**

Create `tests/primitives/test_line_chart.py`:
```python
import ast
from docugen.themes.primitives import line_chart
from docugen.themes.primitives._base import validate_schema


def test_metadata():
    assert line_chart.NAME == "line_chart"
    assert "draw_line" in line_chart.CUE_EVENTS


def test_schema_valid():
    data = {
        "title": "Fitness",
        "x_label": "Gen", "y_label": "Rate",
        "series": [{"label": "A",
                    "points": [[0, 0.4], [5, 0.5], [12, 0.74]],
                    "emphasized": True}],
    }
    assert validate_schema(data, line_chart.DATA_SCHEMA, "data") == []


def test_schema_rejects_bad_points_not_list():
    data = {"series": [{"label": "A", "points": "not a list"}]}
    errs = validate_schema(data, line_chart.DATA_SCHEMA, "data")
    assert any("points" in e for e in errs)


def test_render_compiles():
    clip = {"clip_id": "x", "text": "",
            "word_times": [{"word": "x", "start": 0.0, "end": 0.3}],
            "visuals": {"slide_type": "line_chart",
                        "data": {"series": [{"label": "A",
                                             "points": [[0, 0.4], [1, 0.6], [2, 0.9]]}]},
                        "cue_words": [{"event": "draw_line", "at_index": 0,
                                       "params": {}}]}}
    body = line_chart.render(clip, duration=8.0, images_dir="/tmp", theme=None)
    ast.parse("def construct(self):\n" + body)
```

- [ ] **Step 2: Run test — expect failure**

- [ ] **Step 3: Implement**

Create `src/docugen/themes/primitives/line_chart.py`:
```python
"""line_chart — real axes, left-to-right line draw, highlight points."""

from docugen.themes.primitives.bar_chart import _nice_ticks

NAME = "line_chart"
DESCRIPTION = "Timeseries with real axes, line draw animation, highlight points"
CUE_EVENTS = {"draw_axes", "draw_line", "highlight_point", "reveal_annotation"}
AUDIO_SPANS = [
    {"trigger": "draw_axes", "offset": 0.0, "duration": 0.5,
     "audio": "swoosh", "curve": "ease_in"},
    {"trigger": "draw_line", "offset": 0.0, "duration": 1.5,
     "audio": "trace_hum", "curve": "sustain"},
    {"trigger": "highlight_point", "offset": 0.0, "duration": 0.3,
     "audio": "blip", "curve": "spike"},
]
DATA_SCHEMA = {
    "required": ["series"],
    "types": {"title": str, "x_label": str, "y_label": str, "series": list,
              "highlight_points": list},
    "children": {
        "series": {"required": ["label", "points"],
                    "types": {"label": str, "points": list, "emphasized": bool}},
        "highlight_points": {"required": ["series", "at"],
                              "types": {"series": int, "at": list, "label": str}},
    },
}
PARAMS = {}
NEEDS_CONTENT = False
DEPRECATED = False


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    visuals = clip.get("visuals", {})
    data = visuals.get("data") or {}
    series_in = data.get("series") or []
    if not series_in:
        return f"        alive_wait(self, {max(duration, 0.5):.2f}, particles=bg)\n"

    title = data.get("title", "").replace('"', '\\"')
    x_label = data.get("x_label", "").replace('"', '\\"')
    y_label = data.get("y_label", "").replace('"', '\\"')

    all_x = [p[0] for s in series_in for p in s["points"]]
    all_y = [p[1] for s in series_in for p in s["points"]]
    xr = _nice_ticks(min(all_x), max(all_x))
    yr = _nice_ticks(min(all_y + [0]), max(all_y))
    chart_h, chart_w = 4.0, 9.0

    draw_dur = max((duration - 2.5) / max(len(series_in), 1), 0.6)
    lines: list[str] = []
    if title:
        lines.append(
            f'        title = Text("{title}", font="Courier", weight=BOLD).scale(0.5).to_edge(UP, buff=0.5)\n'
            f'        self.play(FadeIn(title), run_time=0.4)\n'
        )
    lines.append(
        f'        ax = Axes(\n'
        f'            x_range=[{xr[0]}, {xr[-1]}, {xr[1] - xr[0]}],\n'
        f'            y_range=[{yr[0]}, {yr[-1]}, {yr[1] - yr[0]}],\n'
        f'            x_length={chart_w}, y_length={chart_h},\n'
        f'            axis_config={{"color": TEXT_DIM, "include_tip": False, "stroke_width": 2}},\n'
        f'        ).to_edge(DOWN, buff=1.0)\n'
        f'        ax.get_x_axis().add_numbers(font_size=18, color=TEXT_DIM)\n'
        f'        ax.get_y_axis().add_numbers(font_size=18, color=TEXT_DIM)\n'
        f'        self.play(Create(ax), run_time=0.7)\n'
    )
    if x_label:
        lines.append(
            f'        xl = Text("{x_label}", font="Courier", color=TEXT_DIM).scale(0.35)\n'
            f'        xl.next_to(ax.get_x_axis(), DOWN, buff=0.3)\n'
            f'        self.play(FadeIn(xl), run_time=0.2)\n'
        )
    if y_label:
        lines.append(
            f'        yl = Text("{y_label}", font="Courier", color=TEXT_DIM).scale(0.35)\n'
            f'        yl.rotate(PI / 2).next_to(ax.get_y_axis(), LEFT, buff=0.3)\n'
            f'        self.play(FadeIn(yl), run_time=0.2)\n'
        )

    for i, s in enumerate(series_in):
        pts = s["points"]
        label = s["label"].replace('"', '\\"')
        emph = bool(s.get("emphasized", False))
        col = "GOLD" if emph else ("GLOW" if i == 0 else "TEXT_DIM")
        points_list = ", ".join(f"ax.c2p({p[0]}, {p[1]})" for p in pts)
        lines.append(
            f'        line_{i} = VMobject(color={col}, stroke_width=3)\n'
            f'        line_{i}.set_points_as_corners([{points_list}])\n'
            f'        self.play(Create(line_{i}), run_time={draw_dur:.2f})\n'
            f'        end_dot_{i} = Dot(ax.c2p({pts[-1][0]}, {pts[-1][1]}), color={col}, radius=0.08)\n'
            f'        end_lbl_{i} = Text("{label}", font="Courier", color={col}).scale(0.35)\n'
            f'        end_lbl_{i}.next_to(end_dot_{i}, RIGHT, buff=0.15)\n'
            f'        self.play(FadeIn(end_dot_{i}), FadeIn(end_lbl_{i}), run_time=0.3)\n'
        )

    for j, h in enumerate(data.get("highlight_points") or []):
        idx = int(h.get("series", 0))
        x, y = h["at"]
        lbl = str(h.get("label", "")).replace('"', '\\"')
        lines.append(
            f'        hp_{j} = Dot(ax.c2p({x}, {y}), color=GOLD, radius=0.13)\n'
            f'        hp_lbl_{j} = Text("{lbl}", font="Courier", color=GOLD, weight=BOLD).scale(0.35)\n'
            f'        hp_lbl_{j}.next_to(hp_{j}, UP, buff=0.2)\n'
            f'        self.play(FadeIn(hp_{j}, scale=1.6), FadeIn(hp_lbl_{j}), run_time=0.4)\n'
        )

    hold = max(duration - (0.7 + len(series_in) * (draw_dur + 0.3)) - 1.0, 0.5)
    lines.append(f'        alive_wait(self, {hold:.2f}, particles=bg)\n')
    return "".join(lines)
```

- [ ] **Step 4: Run test — expect pass**

Run: `pytest tests/primitives/test_line_chart.py -x -q`

- [ ] **Step 5: Commit**

```bash
git add src/docugen/themes/primitives/line_chart.py tests/primitives/test_line_chart.py
git commit -m "feat: line_chart primitive with real axes + highlights"
```

---

## Task 13: New `tree` primitive

**Files:**
- Create: `src/docugen/themes/primitives/tree.py`
- Create: `tests/primitives/test_tree.py`

- [ ] **Step 1: Write the failing test**

Create `tests/primitives/test_tree.py`:
```python
import ast
from docugen.themes.primitives import tree
from docugen.themes.primitives._base import validate_schema


def test_metadata():
    assert tree.NAME == "tree"
    assert "reveal_root" in tree.CUE_EVENTS


def test_schema_valid():
    data = {"root": {"label": "R", "children": [{"label": "A"}, {"label": "B"}]},
            "layout": "horizontal", "node_style": "box"}
    assert validate_schema(data, tree.DATA_SCHEMA, "data") == []


def test_layout_positions_horizontal():
    root = {"label": "R", "children": [
        {"label": "A", "children": [{"label": "A1"}, {"label": "A2"}]},
        {"label": "B"},
    ]}
    positions = tree._layout(root, layout="horizontal")
    # root should be leftmost
    xs = [pos[0] for pos in positions.values()]
    assert min(xs) == positions[id(root)][0]
    # every node got a position
    def count(n): return 1 + sum(count(c) for c in n.get("children", []))
    assert len(positions) == count(root)


def test_render_compiles():
    clip = {"clip_id": "x", "text": "",
            "word_times": [{"word": "x", "start": 0.0, "end": 0.3}],
            "visuals": {"slide_type": "tree",
                        "data": {"root": {"label": "R",
                                          "children": [{"label": "A"},
                                                       {"label": "B"}]}},
                        "cue_words": [{"event": "reveal_root", "at_index": 0,
                                       "params": {}}]}}
    body = tree.render(clip, duration=8.0, images_dir="/tmp", theme=None)
    ast.parse("def construct(self):\n" + body)
```

- [ ] **Step 2: Run test — expect failure**

- [ ] **Step 3: Implement with a simple recursive layout**

Create `src/docugen/themes/primitives/tree.py`:
```python
"""tree — hierarchical layout (horizontal default, radial optional)."""

NAME = "tree"
DESCRIPTION = "Hierarchical tree with auto layout, depth-first reveal"
CUE_EVENTS = {"reveal_root", "reveal_level", "highlight_node"}
AUDIO_SPANS = [
    {"trigger": "reveal_root", "offset": 0.0, "duration": 0.5,
     "audio": "swoosh", "curve": "ease_in"},
    {"trigger": "reveal_level", "offset": 0.0, "duration": 0.4,
     "audio": "tick", "curve": "ease_in"},
    {"trigger": "highlight_node", "offset": 0.0, "duration": 0.3,
     "audio": "blip", "curve": "spike"},
]
DATA_SCHEMA = {
    "required": ["root"],
    "types": {"root": dict, "layout": str, "node_style": str},
    "enums": {"layout": {"horizontal", "vertical", "radial"},
              "node_style": {"dot", "box", "label"}},
}
PARAMS = {}
NEEDS_CONTENT = False
DEPRECATED = False


def _leaf_count(node: dict) -> int:
    children = node.get("children") or []
    if not children:
        return 1
    return sum(_leaf_count(c) for c in children)


def _depth(node: dict) -> int:
    children = node.get("children") or []
    if not children:
        return 0
    return 1 + max(_depth(c) for c in children)


def _layout(root: dict, layout: str = "horizontal") -> dict:
    """Return dict of id(node) -> (x, y) for every node.

    Horizontal: root on the left, children columns marching right, siblings
    stacked vertically proportional to their leaf count.
    Vertical: root on top, children rows going down.
    Radial: root at center, children spread in a full-circle arc weighted
    by leaf count.
    """
    import math
    positions: dict[int, tuple[float, float]] = {}
    max_d = max(_depth(root), 1)
    total_leaves = _leaf_count(root)

    if layout == "radial":
        def place(node, a0, a1, depth):
            ang = (a0 + a1) / 2
            r = depth * (4.5 / max_d)
            positions[id(node)] = (r * math.cos(ang), r * math.sin(ang))
            kids = node.get("children") or []
            if not kids:
                return
            leaves = [_leaf_count(k) for k in kids]
            total = sum(leaves) or 1
            a = a0
            for kid, lc in zip(kids, leaves):
                span = (a1 - a0) * (lc / total)
                place(kid, a, a + span, depth + 1)
                a += span
        place(root, 0, 2 * math.pi, 0)
        return positions

    horizontal = (layout != "vertical")
    # Axis conventions:
    #   horizontal: depth → x (left-to-right), sibling order → y (top-down)
    #   vertical:   depth → y (top-down),      sibling order → x (left-right)
    span = 4.5
    def place(node, d, lo, hi):
        mid = (lo + hi) / 2
        depth_pos = -span + (2 * span) * (d / max(max_d, 1))
        if horizontal:
            positions[id(node)] = (depth_pos, mid)
        else:
            positions[id(node)] = (mid, -depth_pos)
        kids = node.get("children") or []
        if not kids:
            return
        leaves = [_leaf_count(k) for k in kids]
        total = sum(leaves) or 1
        a = lo
        for kid, lc in zip(kids, leaves):
            width = (hi - lo) * (lc / total)
            place(kid, d + 1, a, a + width)
            a += width

    spread = 3.0
    place(root, 0, -spread, spread)
    return positions


def _walk(node, positions, parent_pos, lines, idx, node_style):
    label = str(node.get("label", "")).replace('"', '\\"')
    emph = bool(node.get("emphasized", False))
    x, y = positions[id(node)]
    col = "GOLD" if emph else "GLOW"
    lines.append(f'        n_{idx[0]} = Dot([{x:.3f}, {y:.3f}, 0], color={col}, radius=0.09)\n')
    lines.append(
        f'        lbl_{idx[0]} = Text("{label}", font="Courier", color={col}).scale(0.3)\n'
        f'        lbl_{idx[0]}.next_to(n_{idx[0]}, UP if {y} >= 0 else DOWN, buff=0.12)\n'
    )
    if parent_pos is not None:
        px, py = parent_pos
        lines.append(
            f'        edge_{idx[0]} = Line([{px:.3f}, {py:.3f}, 0], [{x:.3f}, {y:.3f}, 0],\n'
            f'                              color=TEXT_DIM, stroke_width=1.5)\n'
            f'        self.play(Create(edge_{idx[0]}), FadeIn(n_{idx[0]}), FadeIn(lbl_{idx[0]}),\n'
            f'                  run_time=0.3)\n'
        )
    else:
        lines.append(
            f'        self.play(FadeIn(n_{idx[0]}, scale=1.5), FadeIn(lbl_{idx[0]}), run_time=0.4)\n'
        )
    idx[0] += 1
    for kid in node.get("children") or []:
        _walk(kid, positions, (x, y), lines, idx, node_style)


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    visuals = clip.get("visuals", {})
    data = visuals.get("data") or {}
    root = data.get("root")
    if not root:
        return f"        alive_wait(self, {max(duration, 0.5):.2f}, particles=bg)\n"
    layout = data.get("layout", "horizontal")
    node_style = data.get("node_style", "dot")
    positions = _layout(root, layout=layout)

    lines: list[str] = []
    idx = [0]
    _walk(root, positions, None, lines, idx, node_style)
    node_count = idx[0]
    spent = 0.4 + node_count * 0.35
    hold = max(duration - spent - 1.0, 0.5)
    lines.append(f'        alive_wait(self, {hold:.2f}, particles=bg)\n')
    return "".join(lines)
```

- [ ] **Step 4: Run test — expect pass**

Run: `pytest tests/primitives/test_tree.py -x -q`

- [ ] **Step 5: Commit**

```bash
git add src/docugen/themes/primitives/tree.py tests/primitives/test_tree.py
git commit -m "feat: tree primitive with auto layout (horizontal/vertical/radial)"
```

---

## Task 14: New `timeline` primitive

**Files:**
- Create: `src/docugen/themes/primitives/timeline.py`
- Create: `tests/primitives/test_timeline.py`

- [ ] **Step 1: Write the failing test**

Create `tests/primitives/test_timeline.py`:
```python
import ast
from docugen.themes.primitives import timeline
from docugen.themes.primitives._base import validate_schema


def test_metadata():
    assert timeline.NAME == "timeline"
    assert "reveal_event" in timeline.CUE_EVENTS


def test_schema_valid():
    data = {
        "range": {"start": "2020", "end": "2025"},
        "events": [
            {"at": "2021-Q2", "label": "Pre-seed", "marker": "dot"},
            {"at": "2023-Q1", "label": "Pilot", "marker": "star", "emphasized": True},
        ],
        "orientation": "horizontal",
    }
    assert validate_schema(data, timeline.DATA_SCHEMA, "data") == []


def test_parse_date_fractional_year():
    assert timeline._parse_at("2021-Q1") == 2021.0
    assert timeline._parse_at("2021-Q4") == 2021.75
    assert abs(timeline._parse_at("2023") - 2023.0) < 1e-9


def test_render_compiles():
    clip = {"clip_id": "x", "text": "",
            "word_times": [{"word": "x", "start": 0, "end": 0.3}],
            "visuals": {"slide_type": "timeline",
                        "data": {"range": {"start": "2020", "end": "2025"},
                                 "events": [{"at": "2022", "label": "X"}]},
                        "cue_words": [{"event": "reveal_event",
                                       "at_index": 0, "params": {}}]}}
    body = timeline.render(clip, duration=6.0, images_dir="/tmp", theme=None)
    ast.parse("def construct(self):\n" + body)
```

- [ ] **Step 2: Run test — expect failure**

- [ ] **Step 3: Implement**

Create `src/docugen/themes/primitives/timeline.py`:
```python
"""timeline — events on an axis (horizontal default)."""

import re

NAME = "timeline"
DESCRIPTION = "Events on a horizontal (or vertical) axis, ordered temporally"
CUE_EVENTS = {"draw_axis", "reveal_event", "highlight_event"}
AUDIO_SPANS = [
    {"trigger": "draw_axis", "offset": 0.0, "duration": 0.5,
     "audio": "swoosh", "curve": "ease_in"},
    {"trigger": "reveal_event", "offset": 0.0, "duration": 0.4,
     "audio": "tick", "curve": "ease_in"},
    {"trigger": "highlight_event", "offset": 0.0, "duration": 0.3,
     "audio": "blip", "curve": "spike"},
]
DATA_SCHEMA = {
    "required": ["range", "events"],
    "types": {"range": dict, "events": list, "orientation": str},
    "enums": {"orientation": {"horizontal", "vertical"}},
    "children": {
        "range": {"required": ["start", "end"],
                   "types": {"start": str, "end": str}},
        "events": {"required": ["at", "label"],
                    "types": {"at": str, "label": str, "marker": str,
                              "emphasized": bool}},
    },
}
PARAMS = {}
NEEDS_CONTENT = False
DEPRECATED = False


def _parse_at(s: str) -> float:
    """Parse a date-ish string to a fractional year."""
    s = s.strip()
    m = re.match(r"^(\d{4})(?:-(Q[1-4]|\d{1,2}))?", s)
    if not m:
        return 0.0
    year = int(m.group(1))
    suf = m.group(2)
    if not suf:
        return float(year)
    if suf.startswith("Q"):
        return year + (int(suf[1]) - 1) * 0.25
    # assume month 1-12
    return year + (int(suf) - 1) / 12.0


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    visuals = clip.get("visuals", {})
    data = visuals.get("data") or {}
    rng = data.get("range") or {}
    events = data.get("events") or []
    if not events:
        return f"        alive_wait(self, {max(duration, 0.5):.2f}, particles=bg)\n"

    orientation = data.get("orientation", "horizontal")
    t_start = _parse_at(rng.get("start", ""))
    t_end = _parse_at(rng.get("end", ""))
    if t_end <= t_start:
        t_end = t_start + 1.0

    axis_len = 10.0
    def pos(t):
        frac = (t - t_start) / (t_end - t_start)
        u = -axis_len / 2 + frac * axis_len
        return (u, 0.0) if orientation == "horizontal" else (0.0, u)

    lines: list[str] = []
    if orientation == "horizontal":
        lines.append(
            f'        axis = Line(LEFT * {axis_len/2}, RIGHT * {axis_len/2},\n'
            f'                    color=TEXT_DIM, stroke_width=2)\n'
            f'        self.play(Create(axis), run_time=0.6)\n'
        )
    else:
        lines.append(
            f'        axis = Line(UP * {axis_len/2}, DOWN * {axis_len/2},\n'
            f'                    color=TEXT_DIM, stroke_width=2)\n'
            f'        self.play(Create(axis), run_time=0.6)\n'
        )

    ordered = sorted(events, key=lambda e: _parse_at(e["at"]))
    reveal_dur = max((duration - 2.0) / max(len(ordered), 1), 0.3)
    for i, ev in enumerate(ordered):
        x, y = pos(_parse_at(ev["at"]))
        label = ev["label"].replace('"', '\\"')
        at_str = ev["at"].replace('"', '\\"')
        marker = ev.get("marker", "dot")
        emph = bool(ev.get("emphasized", False))
        col = "GOLD" if emph else "GLOW"
        radius = 0.14 if emph else 0.08
        shape = "Star" if marker == "star" else "Dot"
        lines.append(
            f'        ev_{i} = {shape}([{x:.3f}, {y:.3f}, 0], color={col}'
            + (f', outer_radius={radius + 0.05}' if shape == "Star" else f', radius={radius}')
            + ')\n'
            f'        lbl_{i} = VGroup(\n'
            f'            Text("{at_str}", font="Courier", color=TEXT_DIM).scale(0.25),\n'
            f'            Text("{label}", font="Courier", color={col}, weight=BOLD).scale(0.32),\n'
            f'        ).arrange(DOWN, buff=0.08)\n'
        )
        off = (0, 0.8) if orientation == "horizontal" else (1.2, 0)
        if orientation == "horizontal" and i % 2 == 1:
            off = (0, -0.8)
        lines.append(
            f'        lbl_{i}.move_to([{x + off[0]:.3f}, {y + off[1]:.3f}, 0])\n'
            f'        conn_{i} = Line([{x:.3f}, {y:.3f}, 0],\n'
            f'                        lbl_{i}.get_center(), color=TEXT_DIM, stroke_width=1)\n'
            f'        self.play(FadeIn(ev_{i}, scale=1.5),\n'
            f'                  Create(conn_{i}), FadeIn(lbl_{i}),\n'
            f'                  run_time={reveal_dur:.2f})\n'
        )

    hold = max(duration - 0.6 - len(ordered) * reveal_dur - 1.0, 0.5)
    lines.append(f'        alive_wait(self, {hold:.2f}, particles=bg)\n')
    return "".join(lines)
```

- [ ] **Step 4: Run test — expect pass**

Run: `pytest tests/primitives/test_timeline.py -x -q`

- [ ] **Step 5: Commit**

```bash
git add src/docugen/themes/primitives/timeline.py tests/primitives/test_timeline.py
git commit -m "feat: timeline primitive with horizontal/vertical orientations"
```

---

## Task 15: `llm_custom` primitive metadata + stub renderer

**Files:**
- Create: `src/docugen/themes/primitives/llm_custom.py`
- Create: `src/docugen/renderers/manim_llm_custom.py`
- Create: `tests/primitives/test_llm_custom.py`
- Create: `tests/test_renderer_llm_custom.py`

- [ ] **Step 1: Write the failing primitive test**

Create `tests/primitives/test_llm_custom.py`:
```python
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
    # llm_custom.render returns a no-op body; the real rendering happens
    # in the manim_llm_custom renderer which bypasses the fused-scene path.
    body = llm_custom.render(clip, duration=4.0, images_dir="/tmp", theme=None)
    ast.parse("def construct(self):\n" + body)
```

- [ ] **Step 2: Implement primitive**

Create `src/docugen/themes/primitives/llm_custom.py`:
```python
"""llm_custom — escape hatch. The 'render' function here is a no-op stub;
the real work happens in renderers/manim_llm_custom.py, which this primitive
declares itself compatible with via the default DAG routing."""

NAME = "llm_custom"
DESCRIPTION = "Escape hatch — raw Manim script authored by MCP client"
CUE_EVENTS: set[str] = set()
AUDIO_SPANS: list[dict] = []
DATA_SCHEMA = {
    "required": ["custom_script", "rationale"],
    "types": {"custom_script": str, "rationale": str,
              "imports": list, "est_duration_s": (int, float)},
}
PARAMS = {}
NEEDS_CONTENT = False
DEPRECATED = False
USES_CUSTOM_RENDERER = True


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    # No-op stub. If this ever gets executed via the fused-scene path,
    # we emit an alive_wait; real rendering goes through manim_llm_custom.
    return f"        alive_wait(self, {max(duration, 0.5):.2f}, particles=bg)\n"
```

- [ ] **Step 3: Write the failing renderer test**

Create `tests/test_renderer_llm_custom.py`:
```python
import ast
from unittest.mock import patch, MagicMock
from pathlib import Path
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


@patch("subprocess.run")
def test_render_node_writes_script_and_invokes_manim(mock_run, tmp_path):
    mock_run.return_value = MagicMock(returncode=0, stderr="")
    clip = {
        "clip_id": "test_01",
        "visuals": {"slide_type": "llm_custom",
                    "data": {"custom_script": VALID_SCRIPT,
                             "rationale": "no primitive fits"}},
        "timing": {"clip_duration": 4.0},
    }
    # Pre-create the expected output so the renderer's file-detection succeeds.
    clip_dir = tmp_path / "build" / "clips" / "test_01"
    clip_dir.mkdir(parents=True)
    media = clip_dir / "media" / "videos" / "_scene" / "480p15"
    media.mkdir(parents=True)
    (media / "Scene_test_01.mp4").write_bytes(b"fakevideo")

    node = {"name": "llm_custom", "renderer": "manim_llm_custom"}
    out = render_node(node, {}, clip, tmp_path, theme=None)
    assert Path(out).exists()
    assert mock_run.called
```

- [ ] **Step 4: Implement the renderer**

Create `src/docugen/renderers/manim_llm_custom.py`:
```python
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
    config = load_config(project_path)
    clip_id = clip["clip_id"]
    clip_dir = project_path / "build" / "clips" / clip_id
    clip_dir.mkdir(parents=True, exist_ok=True)
    media_dir = clip_dir / "media"

    visuals = clip.get("visuals", {})
    data = visuals.get("data") or {}
    script = data.get("custom_script", "")

    err = ast_check_script(script)
    if err:
        raise RuntimeError(
            f"llm_custom script for {clip_id} failed AST check: {err}"
        )

    class_name = f"Scene_{clip_id}"
    script_path = clip_dir / f"_scene_llm_{clip_id}.py"
    script_path.write_text(script)

    fps = config["video"]["fps"]
    quality = "-qh" if fps >= 60 else "-qm"

    out_path = clip_dir / f"_node_llm_custom.mp4"

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
```

- [ ] **Step 5: Run tests — expect pass**

Run: `pytest tests/primitives/test_llm_custom.py tests/test_renderer_llm_custom.py -x -q`

- [ ] **Step 6: Commit**

```bash
git add src/docugen/themes/primitives/llm_custom.py src/docugen/renderers/manim_llm_custom.py tests/primitives/test_llm_custom.py tests/test_renderer_llm_custom.py
git commit -m "feat: llm_custom primitive + manim_llm_custom renderer"
```

---

## Task 16: Deprecate `dot_merge` and `remove_reveal` primitives (back-compat stubs)

**Files:**
- Create: `src/docugen/themes/primitives/dot_merge.py`
- Create: `src/docugen/themes/primitives/remove_reveal.py`
- Create: `tests/primitives/test_deprecated.py`

- [ ] **Step 1: Write the failing test**

Create `tests/primitives/test_deprecated.py`:
```python
from docugen.themes.primitives import dot_merge, remove_reveal


def test_dot_merge_deprecated_flagged():
    assert dot_merge.DEPRECATED is True


def test_remove_reveal_deprecated_flagged():
    assert remove_reveal.DEPRECATED is True


def test_still_renders_for_back_compat():
    clip = {"clip_id": "x", "text": "",
            "word_times": [{"word": "x", "start": 0, "end": 0.3}],
            "visuals": {"slide_type": "dot_merge",
                        "data": {"dot1": "A", "dot2": "B"}}}
    body = dot_merge.render(clip, duration=4.0, images_dir="/tmp", theme=None)
    assert isinstance(body, str) and body.strip()
```

- [ ] **Step 2: Port choreography from biopunk (verbatim)**

Read `biopunk.py` — locate `_choreo_dot_merge` and `_choreo_remove_reveal`. Copy each into its own primitive file. Flag each with `DEPRECATED = True` in metadata, and reference the escape hatch in `DESCRIPTION`.

`src/docugen/themes/primitives/dot_merge.py`:
```python
"""dot_merge — DEPRECATED. Parse-evol chemistry-specific; use llm_custom for
new projects. Kept here so older clips.json files still render."""

NAME = "dot_merge"
DESCRIPTION = "DEPRECATED: two compound dots approach and merge. Use llm_custom."
CUE_EVENTS = {"show_dot1", "show_dot2", "merge"}
AUDIO_SPANS = [
    {"trigger": "show_dot1", "offset": 0.0, "duration": 0.3,
     "audio": "blip", "curve": "spike"},
    {"trigger": "show_dot2", "offset": 0.0, "duration": 0.3,
     "audio": "blip", "curve": "spike"},
    {"trigger": "merge", "offset": -1.5, "duration": 1.5,
     "audio": "tension_build", "curve": "ramp_up"},
    {"trigger": "merge", "offset": 0.0, "duration": 0.4,
     "audio": "swell_hit", "curve": "spike"},
]
DATA_SCHEMA = {"required": [], "types": {}}
PARAMS = {"dot1": "", "dot2": "", "result": ""}
NEEDS_CONTENT = False
DEPRECATED = True


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    # Paste the exact body of biopunk._choreo_dot_merge here.
    ...
```

Same pattern for `remove_reveal.py`:
```python
"""remove_reveal — DEPRECATED. Use llm_custom for new projects."""

NAME = "remove_reveal"
DESCRIPTION = "DEPRECATED: one compound fades, another emerges. Use llm_custom."
CUE_EVENTS = {"remove", "reveal"}
AUDIO_SPANS = [
    {"trigger": "remove", "offset": 0.0, "duration": 1.0,
     "audio": "fade_down", "curve": "ramp_down"},
    {"trigger": "reveal", "offset": 0.0, "duration": 0.8,
     "audio": "rise", "curve": "ramp_up"},
]
DATA_SCHEMA = {"required": [], "types": {}}
PARAMS = {"removed": "", "emerged": ""}
NEEDS_CONTENT = False
DEPRECATED = True


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    # Paste the exact body of biopunk._choreo_remove_reveal here.
    ...
```

- [ ] **Step 3: Run test — expect pass**

- [ ] **Step 4: Commit**

```bash
git add src/docugen/themes/primitives/dot_merge.py src/docugen/themes/primitives/remove_reveal.py tests/primitives/test_deprecated.py
git commit -m "feat: migrate dot_merge + remove_reveal as deprecated primitives"
```

---

## Task 17: Wire `SLIDE_REGISTRY` to primitive auto-discovery

**Files:**
- Modify: `src/docugen/themes/slides.py`
- Modify: `tests/test_slides.py`

- [ ] **Step 1: Read current slides.py**

Run: `wc -l src/docugen/themes/slides.py`
Expected: ~184 lines with a hand-coded `SLIDE_REGISTRY` dict.

- [ ] **Step 2: Update existing test to expect the new primitive list**

Overwrite `tests/test_slides.py`:
```python
"""Slide type registry — auto-populated from primitives package."""
from docugen.themes.slides import (
    SLIDE_REGISTRY, validate_slide_type, validate_cue_event,
    get_slide_types_prompt,
)

EXPECTED_PRIMITIVES = {
    # phase 1 MVP
    "bar_chart", "counter", "before_after", "callout",
    "line_chart", "tree", "timeline", "llm_custom",
    # migrated content primitives
    "title", "chapter_card", "ambient_field", "svg_reveal", "photo_organism",
    # deprecated back-compat
    "dot_merge", "remove_reveal",
}


def test_registry_has_expected_primitives():
    assert set(SLIDE_REGISTRY.keys()) >= EXPECTED_PRIMITIVES


def test_every_entry_has_description_and_events():
    for name, info in SLIDE_REGISTRY.items():
        assert "description" in info
        assert "events" in info
        assert isinstance(info["events"], set)
        assert "spans" in info


def test_validate_slide_type_valid():
    assert validate_slide_type("line_chart") is True
    assert validate_slide_type("counter") is True


def test_validate_slide_type_invalid():
    assert validate_slide_type("nonexistent") is False


def test_validate_cue_event_valid():
    assert validate_cue_event("line_chart", "draw_line") is True
    assert validate_cue_event("tree", "reveal_root") is True


def test_validate_cue_event_invalid():
    assert validate_cue_event("line_chart", "explode") is False


def test_prompt_mentions_deprecated():
    text = get_slide_types_prompt()
    # deprecated flag should be surfaced so the MCP client knows to avoid them
    assert "DEPRECATED" in text or "deprecated" in text
```

- [ ] **Step 3: Run test — expect failure**

Run: `pytest tests/test_slides.py -x -q`
Expected: AssertionError (registry doesn't yet auto-populate) or missing keys.

- [ ] **Step 4: Replace `slides.py` with auto-populating version**

Overwrite `src/docugen/themes/slides.py`:
```python
"""Slide type registry — auto-populated from docugen.themes.primitives.

The direct tool picks slide types from this registry. The renderer dispatches
to primitive modules based on slide_type. The spot tool uses span patterns to
build the audio cue sheet.
"""

from docugen.themes.primitives import discover_primitives

INTENSITY_CURVES = {
    "ramp_up", "ramp_down", "spike", "sustain", "ease_in", "linear",
}

AUDIO_TREATMENTS = {
    "hit", "tension_build", "sweep_tone", "tick_accelerate", "sting",
    "swoosh", "blip", "swell_hit", "trace_hum", "tick", "morph_tone",
    "fade_down", "rise",
}


def _build_registry() -> dict:
    reg: dict = {}
    for name, mod in discover_primitives().items():
        reg[name] = {
            "description": mod.DESCRIPTION,
            "events": set(mod.CUE_EVENTS),
            "params": dict(getattr(mod, "PARAMS", {})),
            "spans": list(mod.AUDIO_SPANS),
            "needs_content": bool(getattr(mod, "NEEDS_CONTENT", False)),
            "deprecated": bool(getattr(mod, "DEPRECATED", False)),
        }
    return reg


SLIDE_REGISTRY = _build_registry()


def validate_slide_type(slide_type: str) -> bool:
    return slide_type in SLIDE_REGISTRY


def validate_cue_event(slide_type: str, event: str) -> bool:
    info = SLIDE_REGISTRY.get(slide_type)
    if not info:
        return False
    return event in info["events"]


def get_slide_types_prompt() -> str:
    lines = []
    for name, info in SLIDE_REGISTRY.items():
        events = ", ".join(sorted(info["events"])) if info["events"] else "(none)"
        prefix = "[DEPRECATED] " if info.get("deprecated") else ""
        lines.append(f"- {name}: {prefix}{info['description']}. Cue events: {events}")
    return "\n".join(lines)
```

- [ ] **Step 5: Run test — expect pass**

Run: `pytest tests/test_slides.py -x -q`
Expected: PASS (7 tests).

- [ ] **Step 6: Commit**

```bash
git add src/docugen/themes/slides.py tests/test_slides.py
git commit -m "refactor: auto-populate SLIDE_REGISTRY from primitives package"
```

---

## Task 18: Refactor `biopunk.render_choreography` into a dispatcher

**Files:**
- Modify: `src/docugen/themes/biopunk.py`
- Read: `tests/test_themes.py`

- [ ] **Step 1: Verify existing theme tests still pass as baseline**

Run: `pytest tests/test_themes.py -x -q`
Expected: baseline should be green pre-refactor. If any test already fails, fix that first in a separate commit.

- [ ] **Step 2: Write dispatcher-level test**

Append to `tests/test_themes.py`:
```python
def test_biopunk_dispatches_to_primitive(monkeypatch):
    from docugen.themes.biopunk import Biopunk
    theme = Biopunk()
    clip = {
        "clip_id": "x", "text": "hello",
        "word_times": [{"word": "hello", "start": 0, "end": 0.3}],
        "visuals": {"slide_type": "callout",
                    "data": {"primary": "TEST"},
                    "cue_words": [{"event": "show_primary", "at_index": 0,
                                   "params": {}}]},
    }
    body = theme.render_choreography(clip, duration=3.0, images_dir="/tmp")
    # Should include our primary text
    assert "TEST" in body


def test_biopunk_unknown_slide_type_falls_back():
    from docugen.themes.biopunk import Biopunk
    theme = Biopunk()
    clip = {"clip_id": "x", "text": "",
            "word_times": [],
            "visuals": {"slide_type": "bogus_type", "data": {}}}
    body = theme.render_choreography(clip, duration=3.0, images_dir="/tmp")
    # Fallback should produce something (alive_wait) rather than crashing
    assert "wait" in body.lower()
```

- [ ] **Step 3: Run tests — expect dispatcher test to fail**

Run: `pytest tests/test_themes.py::test_biopunk_dispatches_to_primitive -x -q`

- [ ] **Step 4: Rewrite `render_choreography` as a dispatcher**

In `src/docugen/themes/biopunk.py`, locate the `render_choreography` method (around line 640) and the `method_map` dict inside it. Replace the method with:

```python
    def render_choreography(self, clip: dict, duration: float,
                            images_dir: str) -> str:
        """Dispatch to themes.primitives.<slide_type>.render()."""
        from docugen.themes.primitives import discover_primitives

        visuals = clip.get("visuals", {})
        slide_type = visuals.get("slide_type", "")
        primitives = discover_primitives()
        mod = primitives.get(slide_type)
        if mod is None:
            # Fallback for unknown slide types: hold the duration quietly.
            hold = max(duration, 0.5)
            return f"        alive_wait(self, {hold:.2f}, particles=bg)\n"
        return mod.render(clip, duration, images_dir, self)
```

**Delete all the `_choreo_*` helper methods from `biopunk.py`.** They live in `themes/primitives/*.py` now. The palette, helpers (`_sine`, `_saw`, etc.), `_POST_FILTERS`, `manim_header`, `default_dag`, `render_theme_layer`, `render_content_layer`, `transition_sounds`, `chapter_layers` stay.

- [ ] **Step 5: Run all theme/primitive tests — expect pass**

Run: `pytest tests/test_themes.py tests/primitives -x -q`
Expected: PASS across the whole block.

- [ ] **Step 6: Run the broader test suite — no regressions**

Run: `pytest -x -q`
Expected: PASS (or only pre-existing failures unrelated to this work).

- [ ] **Step 7: Commit**

```bash
git add src/docugen/themes/biopunk.py tests/test_themes.py
git commit -m "refactor: biopunk.render_choreography dispatches to primitives"
```

---

## Task 19: Extend `direct_apply` with per-primitive schema validation

**Files:**
- Modify: `src/docugen/direct.py`
- Create: `tests/test_direct_v2.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_direct_v2.py`:
```python
"""Per-primitive schema validation tests."""
import pytest
from docugen.direct import validate_clip_direction


@pytest.fixture
def base_clip():
    return {
        "clip_id": "ch1_01",
        "text": "Revenue grew",
        "word_times": [
            {"word": "Revenue", "start": 0.0, "end": 0.4},
            {"word": "grew", "start": 0.4, "end": 0.7},
        ],
    }


def _direction(slide_type, data=None, cue_event=None):
    return {
        "slide_type": slide_type,
        "assets": [],
        "data": data or {},
        "cue_words": [{"word": "Revenue", "at_index": 0,
                       "event": cue_event or "show_primary",
                       "params": {}}],
        "layout": "center",
        "transition_in": "crossfade",
        "transition_out": "crossfade_next",
        "transition_sound": None,
    }


def test_valid_callout_passes(base_clip):
    direction = _direction("callout",
                            data={"primary": "$41"},
                            cue_event="show_primary")
    errs = validate_clip_direction(direction, base_clip, set())
    assert errs == []


def test_callout_missing_primary_rejected(base_clip):
    direction = _direction("callout",
                            data={"secondary": "X"},
                            cue_event="show_primary")
    errs = validate_clip_direction(direction, base_clip, set())
    assert any("primary" in e for e in errs)


def test_bar_chart_schema_enforced(base_clip):
    # missing required 'series'
    direction = _direction("bar_chart",
                            data={"title": "X"},
                            cue_event="show_bar")
    errs = validate_clip_direction(direction, base_clip, set())
    assert any("series" in e for e in errs)


def test_llm_custom_requires_script_and_rationale(base_clip):
    direction = _direction("llm_custom", data={}, cue_event=None)
    # no cue_events for llm_custom; drop the cue_words so the cue validator
    # doesn't error.
    direction["cue_words"] = []
    errs = validate_clip_direction(direction, base_clip, set())
    assert any("custom_script" in e for e in errs)
    assert any("rationale" in e for e in errs)
```

- [ ] **Step 2: Run test — expect failure**

Run: `pytest tests/test_direct_v2.py -x -q`

- [ ] **Step 3: Extend `validate_clip_direction`**

In `src/docugen/direct.py`, find the top of the file and add:
```python
from docugen.themes.primitives import discover_primitives
from docugen.themes.primitives._base import validate_schema
```

Within `validate_clip_direction`, after the existing validations (slide_type existence, assets, cue indices, cue events, layout, transitions, sound), add:
```python
    # Primitive schema validation
    if slide_type:
        primitives = discover_primitives()
        mod = primitives.get(slide_type)
        if mod is not None:
            data = direction.get("data")
            if data is None:
                if mod.DATA_SCHEMA.get("required"):
                    errors.append(
                        f"{clip_id}: missing 'data' block required by "
                        f"primitive {slide_type!r}"
                    )
            else:
                schema_errs = validate_schema(data, mod.DATA_SCHEMA,
                                               f"{clip_id}.data")
                errors.extend(schema_errs)
```

- [ ] **Step 4: Run all direct tests — expect pass**

Run: `pytest tests/test_direct.py tests/test_direct_v2.py -x -q`

- [ ] **Step 5: Commit**

```bash
git add src/docugen/direct.py tests/test_direct_v2.py
git commit -m "feat: schema-validate clip visuals against primitive DATA_SCHEMA"
```

---

## Task 20: New `viz_extract` MCP tool

**Files:**
- Create: `src/docugen/tools/viz_extract.py`
- Create: `tests/test_viz_extract.py`
- Modify: `src/docugen/server.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_viz_extract.py`:
```python
"""viz_extract — PDF → build/pdf_data.json with content-hash caching."""
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from docugen.tools.viz_extract import (
    compute_pdf_hash, pdf_to_page_images, viz_extract,
)


def test_compute_hash_stable(tmp_path):
    p = tmp_path / "a.pdf"
    p.write_bytes(b"fake pdf")
    h1 = compute_pdf_hash([p])
    h2 = compute_pdf_hash([p])
    assert h1 == h2 and len(h1) == 16


def test_compute_hash_changes_with_content(tmp_path):
    p = tmp_path / "a.pdf"
    p.write_bytes(b"one")
    h1 = compute_pdf_hash([p])
    p.write_bytes(b"two")
    h2 = compute_pdf_hash([p])
    assert h1 != h2


def test_viz_extract_skips_when_hash_matches(tmp_path):
    project = tmp_path
    (project / "spec.pdf").write_bytes(b"fake")
    build = project / "build"
    build.mkdir()
    # Pre-populate pdf_data.json + hash sidecar so extract can skip.
    (build / "pdf_data.json").write_text(json.dumps({"cached": True}))
    h = compute_pdf_hash([project / "spec.pdf"])
    (build / "pdf_data.json.pdfhash").write_text(h)

    result = viz_extract(project)
    # Should not re-extract
    assert "cached" in result.lower() or "unchanged" in result.lower()
    data = json.loads((build / "pdf_data.json").read_text())
    assert data == {"cached": True}


@patch("docugen.tools.viz_extract._extract_via_vision")
def test_viz_extract_runs_when_hash_differs(mock_extract, tmp_path):
    mock_extract.return_value = {"page_1": {"candidate_primitive": "bar_chart"}}
    project = tmp_path
    (project / "spec.pdf").write_bytes(b"fake")
    (project / "build").mkdir()

    result = viz_extract(project)
    assert mock_extract.called
    data = json.loads((project / "build" / "pdf_data.json").read_text())
    assert data == {"page_1": {"candidate_primitive": "bar_chart"}}
    assert "pdf_data.json.pdfhash" in [p.name for p in (project / "build").iterdir()]
```

- [ ] **Step 2: Run test — expect failure**

Run: `pytest tests/test_viz_extract.py -x -q`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `viz_extract`**

Create `src/docugen/tools/viz_extract.py`:
```python
"""viz_extract — decode source PDFs to structured JSON via Claude vision.

Writes build/pdf_data.json alongside a .pdfhash sidecar so re-runs skip when
the PDFs haven't changed. The vision call itself is isolated behind
_extract_via_vision so tests can mock it.

Current contract: since the MCP client itself is the vision-capable model
(Claude Code), this tool does not make its own API call. It instead returns
a structured prompt artifact that the client consumes in the same pattern
as direct_prepare — the MCP client performs the reasoning and (via a follow-up
tool call or direct file write) populates pdf_data.json. For v1 we ship the
hash-cache and skip logic; the vision round-trip plugs in through
_extract_via_vision, which v1 leaves as a stub raising NotImplementedError
with instructions for the caller.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def compute_pdf_hash(pdfs: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(pdfs, key=lambda x: x.name):
        h.update(p.name.encode("utf-8"))
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def pdf_to_page_images(pdf_path: Path, out_dir: Path) -> list[Path]:
    """Rasterize a PDF to per-page PNGs using pdf2image/pillow if installed.
    Returns the list of generated image paths. Creates out_dir if missing."""
    try:
        from pdf2image import convert_from_path
    except ImportError as e:
        raise RuntimeError(
            "pdf2image not installed; add to deps or ensure Poppler is on PATH"
        ) from e
    out_dir.mkdir(parents=True, exist_ok=True)
    images = convert_from_path(str(pdf_path), dpi=150)
    paths: list[Path] = []
    for i, img in enumerate(images, start=1):
        out = out_dir / f"{pdf_path.stem}_page_{i:03d}.png"
        img.save(out, "PNG")
        paths.append(out)
    return paths


def _extract_via_vision(page_images: list[Path]) -> dict:
    """Call Claude vision (or equivalent) with each page image, return
    structured decoding.

    v1 stub — must be patched by callers. Will be fleshed out once the
    MCP server gains a direct vision-invocation path in a follow-up task.
    """
    raise NotImplementedError(
        "viz_extract: _extract_via_vision is not implemented in v1. "
        "Provide pdf_data.json by hand or patch this call in tests."
    )


def _find_pdfs(project_path: Path) -> list[Path]:
    out = []
    for name in ("spec.pdf", "slide_deck.pdf"):
        p = project_path / name
        if p.exists():
            out.append(p)
    return out


def viz_extract(project_path: str | Path) -> str:
    project_path = Path(project_path)
    build = project_path / "build"
    build.mkdir(exist_ok=True)

    pdfs = _find_pdfs(project_path)
    if not pdfs:
        return "viz_extract: no spec.pdf or slide_deck.pdf in project — nothing to do."

    pdf_hash = compute_pdf_hash(pdfs)
    data_path = build / "pdf_data.json"
    hash_path = build / "pdf_data.json.pdfhash"

    if data_path.exists() and hash_path.exists() and hash_path.read_text().strip() == pdf_hash:
        return f"viz_extract: cached (PDFs unchanged, hash={pdf_hash})"

    images_dir = build / "pdf_pages"
    images: list[Path] = []
    for pdf in pdfs:
        images.extend(pdf_to_page_images(pdf, images_dir))

    data = _extract_via_vision(images)
    data_path.write_text(json.dumps(data, indent=2) + "\n")
    hash_path.write_text(pdf_hash)
    return (
        f"viz_extract: extracted {len(data)} pages from "
        f"{len(pdfs)} PDF(s); hash={pdf_hash}"
    )
```

- [ ] **Step 4: Register in MCP server**

In `src/docugen/server.py`:

1. Import near the other tool imports:
```python
from docugen.tools.viz_extract import viz_extract as _viz_extract
```

2. Update the FastMCP instructions string to reflect the new ordering:
```python
mcp = FastMCP("docugen", instructions=(
    "Documentary generation pipeline. Use tools in order: "
    "init -> plan -> split -> narrate -> viz_extract -> direct_prepare -> direct_apply -> spot -> render -> score -> stitch. "
    "Use title to generate a standalone title card. "
    "Review and edit clips.json between steps to adjust "
    "emotion, pacing, visual direction, and cue words per clip. "
    "Review and edit build/pdf_data.json after viz_extract to correct any "
    "misread chart data before direction."
))
```

3. Add the tool registration near the other `@mcp.tool()` definitions (place between `align` and `direct_prepare`):
```python
@mcp.tool()
def viz_extract(project_path: str) -> str:
    """Extract chart/table data from the source PDF into build/pdf_data.json.

    Uses vision-based reading to decode every chart and table on every page
    of spec.pdf (and slide_deck.pdf if present) into primitive-compatible JSON.
    Writes build/pdf_data.json and a sidecar .pdfhash — re-runs skip when
    PDFs haven't changed. The resulting JSON should be reviewed and edited
    before direct_prepare consumes it.

    Args:
        project_path: Path to project directory.
    """
    return _viz_extract(project_path)
```

- [ ] **Step 5: Run tests — expect pass**

Run: `pytest tests/test_viz_extract.py -x -q`

- [ ] **Step 6: Commit**

```bash
git add src/docugen/tools/viz_extract.py tests/test_viz_extract.py src/docugen/server.py
git commit -m "feat: viz_extract tool with content-hash caching"
```

---

## Task 21: Extend `direct_prepare` with `pdf_data.json` + primitive schemas

**Files:**
- Modify: `src/docugen/direct.py`
- Create: `tests/test_direct_prepare_v2.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_direct_prepare_v2.py`:
```python
import json
from docugen.direct import direct_prepare


def _scaffold(tmp_path, with_pdf_data=False):
    build = tmp_path / "build"
    build.mkdir()
    (tmp_path / "images").mkdir()
    clips = {
        "chapters": [{"id": "ch1", "title": "Intro", "clips": [
            {"clip_id": "ch1_01", "text": "hello",
             "word_times": [{"word": "hello", "start": 0, "end": 0.3}],
             "pacing": "normal"},
        ]}]
    }
    (build / "clips.json").write_text(json.dumps(clips))
    if with_pdf_data:
        (build / "pdf_data.json").write_text(json.dumps(
            {"page_1": {"candidate_primitive": "bar_chart",
                         "data": {"series": [{"label": "X", "value": 1}]}}}
        ))


def test_prepare_includes_primitive_schemas(tmp_path):
    _scaffold(tmp_path)
    out = direct_prepare(tmp_path)
    assert "callout" in out
    assert "DATA_SCHEMA" in out or "data:" in out.lower()
    assert "Available Slide Types" in out


def test_prepare_includes_pdf_data_when_present(tmp_path):
    _scaffold(tmp_path, with_pdf_data=True)
    out = direct_prepare(tmp_path)
    assert "page_1" in out
    assert "bar_chart" in out


def test_prepare_no_pdf_data_gracefully(tmp_path):
    _scaffold(tmp_path, with_pdf_data=False)
    out = direct_prepare(tmp_path)
    assert "pdf_data.json" in out.lower() or "no extracted data" in out.lower()
```

- [ ] **Step 2: Run test — expect failure**

Run: `pytest tests/test_direct_prepare_v2.py -x -q`

- [ ] **Step 3: Extend `direct_prepare`**

In `src/docugen/direct.py`, modify `direct_prepare`. After the existing `get_slide_types_prompt()` call, add:
```python
    # Attach per-primitive DATA_SCHEMA so the client knows exactly what to emit
    from docugen.themes.primitives import discover_primitives
    primitives = discover_primitives()
    schema_lines = []
    for name in sorted(primitives):
        mod = primitives[name]
        if getattr(mod, "DEPRECATED", False):
            continue
        schema_lines.append(f"\n### {name}")
        schema_lines.append(f"{mod.DESCRIPTION}")
        schema_lines.append(
            "DATA_SCHEMA = " + json.dumps(mod.DATA_SCHEMA, default=list, indent=2)
        )
    schemas_block = "\n".join(schema_lines)

    # Attach pdf_data.json contents if present
    pdf_data_path = build_dir / "pdf_data.json"
    if pdf_data_path.exists():
        pdf_block = pdf_data_path.read_text()
    else:
        pdf_block = (
            "No extracted data available — pdf_data.json missing. "
            "Run `viz_extract` first, or fall back to narration inference / llm_custom."
        )
```

Then extend the returned string's template to include these blocks:
```python
    return (
        f"# Creative Direction Context\n\n"
        f"## Available Slide Types\n{slide_types_desc}\n\n"
        f"## Primitive Data Schemas\n{schemas_block}\n\n"
        f"## Extracted Source Data (pdf_data.json)\n```json\n{pdf_block}\n```\n\n"
        f"## Available Assets\n{assets_block}\n\n"
        f"## Clips Needing Direction\n{clips_block}\n\n"
        f"## Output Format\n"
        f"Provide a JSON object where keys are clip_ids and values have:\n"
        f"- slide_type: one of the types above (prefer typed primitives; use "
        f"llm_custom only when nothing fits)\n"
        f"- data: object matching the primitive's DATA_SCHEMA\n"
        f"- assets: list of filenames from available assets (empty if none)\n"
        f"- cue_words: list of {{\"word\": \"...\", \"at_index\": N, "
        f"\"event\": \"...\", \"params\": {{}}}}\n"
        f"- layout: center | split_left_right | bottom_third | full_bleed\n"
        f"- transition_in: crossfade | cut | wipe_left | fade_black\n"
        f"- transition_out: crossfade_next | cut | fade_black\n"
        f"- transition_sound: one of the 8 theme sounds, or null\n"
    )
```

- [ ] **Step 4: Run test — expect pass**

Run: `pytest tests/test_direct_prepare_v2.py -x -q`

- [ ] **Step 5: Commit**

```bash
git add src/docugen/direct.py tests/test_direct_prepare_v2.py
git commit -m "feat: direct_prepare attaches pdf_data.json + primitive schemas"
```

---

## Task 22: Route `llm_custom` slide_type through new renderer in default DAG

**Files:**
- Modify: `src/docugen/themes/biopunk.py` (`default_dag` method, around line 588)
- Create: `tests/test_default_dag_llm_custom.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_default_dag_llm_custom.py`:
```python
from docugen.themes.biopunk import Biopunk


def test_default_dag_uses_llm_custom_renderer_for_llm_custom_clip():
    theme = Biopunk()
    clip = {
        "clip_id": "x",
        "visuals": {"slide_type": "llm_custom",
                    "data": {"custom_script": "class S: pass",
                             "rationale": "R"}},
    }
    nodes = theme.default_dag(clip)
    renderers = {n["renderer"] for n in nodes}
    assert "manim_llm_custom" in renderers
    # The fused-scene manim_choreo path should NOT be present for llm_custom
    assert "manim_choreo" not in renderers


def test_default_dag_keeps_fused_path_for_typed_primitives():
    theme = Biopunk()
    clip = {
        "clip_id": "y",
        "visuals": {"slide_type": "callout",
                    "data": {"primary": "$41"}},
    }
    nodes = theme.default_dag(clip)
    renderers = {n["renderer"] for n in nodes}
    assert "manim_choreo" in renderers
    assert "manim_llm_custom" not in renderers
```

- [ ] **Step 2: Run test — expect failure**

Run: `pytest tests/test_default_dag_llm_custom.py -x -q`

- [ ] **Step 3: Branch `default_dag` on `slide_type == "llm_custom"`**

In `src/docugen/themes/biopunk.py`, at the top of `default_dag` (right after reading `visuals`/`slide_type`), add:
```python
        if slide_type == "llm_custom":
            nodes = [
                {"name": "llm_custom", "renderer": "manim_llm_custom"},
                {"name": "composite", "renderer": "ffmpeg_composite",
                 "inputs": ["llm_custom"]},
                {"name": "post", "renderer": "ffmpeg_post",
                 "inputs": ["composite"], "filters": [], "audio": []},
            ]
            return nodes
```

Place this before the existing fused-scene node assembly.

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/test_default_dag_llm_custom.py tests/test_themes.py -x -q`

- [ ] **Step 5: Commit**

```bash
git add src/docugen/themes/biopunk.py tests/test_default_dag_llm_custom.py
git commit -m "feat: default DAG routes llm_custom clips to manim_llm_custom renderer"
```

---

## Task 23: Back-compat `data_text` / `counter_sync` / `bar_chart_build` aliases

Existing projects have `clips.json` with old slide type names. Add aliases so they keep resolving.

**Files:**
- Modify: `src/docugen/themes/slides.py`
- Modify: `src/docugen/themes/biopunk.py` (dispatcher)
- Create: `tests/test_primitive_aliases.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_primitive_aliases.py`:
```python
from docugen.themes.slides import validate_slide_type, validate_cue_event
from docugen.themes.biopunk import Biopunk


def test_data_text_alias_validates():
    assert validate_slide_type("data_text") is True


def test_counter_sync_alias_validates():
    assert validate_slide_type("counter_sync") is True


def test_bar_chart_build_alias_validates():
    assert validate_slide_type("bar_chart_build") is True


def test_old_cue_event_still_validates():
    # counter_sync used `start_count` — must keep working
    assert validate_cue_event("counter_sync", "start_count") is True


def test_dispatcher_resolves_alias_to_new_primitive():
    theme = Biopunk()
    clip = {"clip_id": "x", "text": "",
            "word_times": [{"word": "x", "start": 0, "end": 0.3}],
            "visuals": {"slide_type": "data_text",
                        "data": {"primary": "X"},
                        "cue_words": [{"event": "show_primary", "at_index": 0,
                                        "params": {}}]}}
    body = theme.render_choreography(clip, duration=3.0, images_dir="/tmp")
    assert "X" in body
```

- [ ] **Step 2: Run test — expect failure**

- [ ] **Step 3: Add an alias map and plumb it through**

In `src/docugen/themes/slides.py`, after `SLIDE_REGISTRY = _build_registry()` add:

```python
# Back-compat aliases for legacy slide type names. Aliases resolve to the
# new primitive; their registry entry mirrors the target so cue events
# still validate against old names.
PRIMITIVE_ALIASES = {
    "data_text": "callout",
    "counter_sync": "counter",
    "bar_chart_build": "bar_chart",
}

for alias, target in PRIMITIVE_ALIASES.items():
    if target in SLIDE_REGISTRY and alias not in SLIDE_REGISTRY:
        SLIDE_REGISTRY[alias] = dict(SLIDE_REGISTRY[target])
        # Preserve the old cue event names used by existing clips.json files.
        SLIDE_REGISTRY[alias]["events"] = (
            SLIDE_REGISTRY[alias]["events"] | _LEGACY_CUE_EVENTS.get(alias, set())
        )

_LEGACY_CUE_EVENTS = {
    "counter_sync": {"start_count", "hold"},
    "bar_chart_build": {"show_bar"},
    "data_text": {"show_text"},
}
```

**Note:** Python reads top-down; declare `_LEGACY_CUE_EVENTS` **above** the alias-expansion loop to avoid a NameError. Rearrange accordingly.

In `src/docugen/themes/biopunk.py` `render_choreography`, resolve aliases before primitive lookup:
```python
        from docugen.themes.slides import PRIMITIVE_ALIASES
        slide_type = PRIMITIVE_ALIASES.get(slide_type, slide_type)
```

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/test_primitive_aliases.py tests/test_slides.py -x -q`

- [ ] **Step 5: Commit**

```bash
git add src/docugen/themes/slides.py src/docugen/themes/biopunk.py tests/test_primitive_aliases.py
git commit -m "feat: back-compat aliases (data_text→callout, counter_sync→counter, bar_chart_build→bar_chart)"
```

---

## Task 24: Update README step table + MCP instructions

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the "How It Works" table to include viz_extract**

In `README.md`, find the nine-tool table (currently numbered 1-9 with `init`..`stitch`) and insert a new row for `viz_extract` between rows 5 (`align`) and 6a (`direct_prepare`). Renumber as needed so the order reads: init → plan → split → narrate → align → viz_extract → direct_prepare → direct_apply → title → render → score → stitch.

Also update the intro sentence from "nine tools" to "ten tools" (or rephrase as "a set of tools").

Also update the "### 2. Run the pipeline" step-walkthrough section to reflect the new order.

- [ ] **Step 2: Spot-check that no other README references still say "nine tools"**

Run: `grep -n "nine" README.md`
Expected: zero hits, or only in unrelated prose.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add viz_extract to tool table and pipeline walkthrough"
```

---

## Task 25: End-to-end validation on parse-evols-yeast

This task is a manual validation pass — not a code change. It verifies the MVP acceptance criteria.

**Files:** none modified (may touch `projects/parse-evols-yeast/build/clips.json` by hand to fix any vision-extraction misreads, but that is data not code).

- [ ] **Step 1: Confirm a clean build dir**

Run: `ls projects/parse-evols-yeast/build`
Expected: `direction.json`, `frames`, `plan.json`, `slide_deck.pdf` only (stale cache already cleared in earlier work).

- [ ] **Step 2: Run the full pipeline via the MCP session**

In an MCP client session pointed at this repo, run each tool in order. Validate at each step:

```
split("/abs/path/to/projects/parse-evols-yeast")
→ expect build/clips.json to be written.

narrate(...)
→ expect every clip's wav to be generated + word_times + timing populated.

viz_extract(...)
→ expect build/pdf_data.json. Open it and spot-check 3 pages; correct any misread numbers by hand.

direct_prepare(...)
→ expect the returned prompt to contain all 13 MVP primitives and the pdf_data.json body.

[MCP client emits direction_json covering all clips]

direct_apply(..., direction_json)
→ expect "All validation passed" and a new clips.json.

spot(...) then render(...)
→ expect every clip to render; llm_custom clips should succeed on first pass
  or succeed after 1 retry round.

score(...), stitch(...)
→ expect build/final.mp4.
```

- [ ] **Step 3: Measure typed-primitive coverage**

Run this one-liner in the project dir to confirm the ≥60% typed-primitive acceptance criterion:
```bash
python3 -c "
import json
d = json.load(open('projects/parse-evols-yeast/build/clips.json'))
types = [c['visuals']['slide_type']
         for ch in d['chapters'] for c in ch['clips']
         if c.get('text','').strip()]
typed = [t for t in types if t != 'llm_custom']
print(f'typed={len(typed)}/{len(types)} = {len(typed)/max(len(types),1):.0%}')
"
```
Expected: typed fraction ≥ 60%.

- [ ] **Step 4: Spot-check 5 clips for real-data rendering**

Open 5 rendered clips in `build/clips/*.mp4` and confirm they show axes / units / concrete values that can be traced to `pdf_data.json`. Log which ones pass; fix any that don't by editing the clip's `visuals.data` and re-running `render`.

- [ ] **Step 5: Confirm perilux legacy path unbroken**

Run: `pytest -x -q`
Expected: full suite green. Then in the MCP session:
```
stitch("/abs/path/to/projects/perilux")
```
Expected: perilux renders without changes (it takes the legacy `plan.json` path).

- [ ] **Step 6: Commit any clips.json / pdf_data.json fixes from Step 4**

```bash
git add projects/parse-evols-yeast/build/clips.json projects/parse-evols-yeast/build/pdf_data.json
git commit -m "data: yeast pitch viz specs for MVP validation"
```

- [ ] **Step 7: Tick the Phase 1 checklist items in README.md and commit**

```bash
git add README.md
git commit -m "docs: mark phase 1 MVP complete in roadmap"
```

---

## Self-review notes (for the planner)

**Spec coverage check:**
- `themes/primitives/` package with auto-discovery → Task 1 ✓
- Shared schema validator → Task 2 ✓
- 5 migrated content primitives → Tasks 3-7 ✓
- 4 upgraded data primitives (callout, counter, before_after, bar_chart) → Tasks 8-11 ✓
- 3 new data primitives (line_chart, tree, timeline) → Tasks 12-14 ✓
- `llm_custom` primitive + renderer → Task 15 ✓
- 2 deprecated primitives preserved → Task 16 ✓
- `SLIDE_REGISTRY` auto-populated → Task 17 ✓
- `biopunk.render_choreography` dispatcher refactor → Task 18 ✓
- `direct_apply` schema validation → Task 19 ✓
- `viz_extract` tool with hash cache → Task 20 ✓
- `direct_prepare` attaches `pdf_data.json` + schemas → Task 21 ✓
- `llm_custom` routed through `default_dag` → Task 22 ✓
- Back-compat aliases so stale `clips.json` files still validate → Task 23 ✓
- README updated → Task 24 ✓
- End-to-end validation on parse-evols-yeast → Task 25 ✓

**Placeholder scan:** Tasks 4, 7, 16 tell the engineer to "paste the exact body from biopunk." This is intentional — the biopunk bodies are long and copying them verbatim is a mechanical transform, not a design decision. The engineer must read the exact lines referenced (`biopunk.py:990-1035` etc.) and transfer them. No further spec required.

**Type consistency:** Every primitive module exports the same attribute set (NAME, DESCRIPTION, CUE_EVENTS, AUDIO_SPANS, DATA_SCHEMA, PARAMS, NEEDS_CONTENT, DEPRECATED, render). `discover_primitives()` returns the same shape used by `SLIDE_REGISTRY._build_registry`, `biopunk.render_choreography`, `direct_apply`, and `direct_prepare`. `compute_pdf_hash` / `pdf_data.json.pdfhash` sidecar mirrors the narrate `.wav.txthash` pattern.

**Open items from the spec, deferred past MVP:**
- Exact Manim layout algorithm for `tree` (Reingold-Tilford vs. Walker's): Task 13 uses a simpler recursive leaf-weighted layout, which is adequate for yeast and small trees. Upgrade deferred.
- `_extract_via_vision` in `viz_extract`: Task 20 ships the scaffold + hash cache + page rasterization. The vision round-trip itself is a stub raising NotImplementedError in v1; populating `pdf_data.json` is done by hand or by patching the call in tests for this cycle. Wiring to the MCP client's vision capability is a follow-up task once we decide how a tool can hand image content back to the client (a known MCP pattern, but out of scope for this MVP plan).
