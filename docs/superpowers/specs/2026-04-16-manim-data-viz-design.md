# Manim Data Visualization Rebuild — Design Spec

**Date:** 2026-04-16
**Status:** Approved, awaiting implementation plan
**Motivation:** Current slide-type grammar produces generic, repetitive visuals with no real data. A ~22-primitive typed grammar + PDF extraction + LLM escape hatch replaces it.

---

## Problem

The existing viz grammar in `themes/slides.py` has 11 slide types, of which only ~3 are data-aware:

- `bar_chart_build` — no axes, no units, hardcoded scale factor (`value / 25000 * 8`). Renders bars but not a chart.
- `counter_sync` — single-scalar animation. No units/suffix support.
- `before_after` — two values with arrow. No % change, no magnitude, no context.
- `data_text` — text on screen, mislabeled as data.

Source PDFs contain real charts and tables, but nothing extracts them. Every data-bearing clip ends up visually identical regardless of the narration.

## Goals

1. Replace generic templates with a grammar of **real data viz primitives** — each renders proper axes, units, and source data.
2. Ground visuals in the source material via a **PDF extraction step** that decodes charts/tables to structured JSON.
3. Preserve per-clip bespoke capability via an **LLM escape hatch** for clips that don't fit the grammar.
4. Keep the existing MCP pipeline and DAG cache intact; this is additive/substitutive, not an architectural rewrite.

## Non-goals

- Multi-theme support (phase 3).
- Migrating `perilux` off the legacy `plan.json` path (phase 3).
- Replacing Manim with matplotlib/plotly (phase 3 fallback, not default).

---

## Architecture

```
[spec.pdf, slide_deck.pdf]
            │
            ▼
     viz_extract (NEW) ──► build/pdf_data.json
            │                  (structured, reviewable)
            ▼
  direct_prepare (extended) ──► tool result = narration context
            │                                 + primitive schemas
            │                                 + pdf_data.json
            ▼
  MCP client emits clip.visuals per clip
            │
            ▼
   direct_apply (extended) ──► schema validation + timing
            │
            ▼
     spot → render → score → stitch  (existing, unchanged)
```

### New components

**`tools/viz_extract.py`** — MCP tool.
- Input: project path.
- Process: Reads PDFs in the project, sends page images to Claude vision in a single call, parses back structured decoding per page (figures, charts, tables).
- Output: `build/pdf_data.json`. Sidecar hash (`pdf_data.json.pdfhash`) keyed on input PDF content so re-runs skip work when the PDF hasn't changed.
- Called between `narrate` and `direct_prepare`.

**`themes/primitives/` package.**
- One file per primitive. Each exports `SCHEMA`, `CUE_EVENTS`, `AUDIO_SPANS`, and `render(clip, duration, images_dir, theme)`.
- `themes/primitives/__init__.py` auto-discovers modules at import time and populates `SLIDE_REGISTRY` — registry is no longer a hand-maintained dict.

**`renderers/manim_llm_custom.py`** — escape-hatch renderer.
- Takes `clip.visuals.data.custom_script`, writes to disk, runs `manim --disable_caching`.
- On compile/render failure: re-invokes the MCP client with the traceback, requests a fixed script. Max 3 retries, then fails the clip with a clear error.
- Participates in the existing DAG + content-hash cache (script content is hashed).

### Changed components

**`direct.py:direct_prepare`** — returns `pdf_data.json` + per-primitive JSON schemas + existing narration context. PDF page images no longer attached (the extraction step already read them).

**`direct.py:direct_apply`** — validates each clip's `visuals.data` against its primitive's schema. For `llm_custom`, does an AST-level compile check (no render). Computes timing as it does today.

**`themes/biopunk.py`** — `render_choreography` becomes a thin dispatcher. The ~500 lines of `_choreo_*` methods move into `themes/primitives/*.py` files. Palette and helper functions stay in biopunk.

**`themes/slides.py`** — `SLIDE_REGISTRY` auto-built from `themes/primitives/*.py` at import time. `INTENSITY_CURVES` and `AUDIO_TREATMENTS` constants stay.

**`server.py`** — new `viz_extract` tool registered, ordering updated in MCP instructions.

### Unchanged components

- `compose.py` — DAG orchestration, content hashing, fusion groups all work as-is.
- `split.py`, `align.py`, `timing.py`, `spot.py`, `score.py`, `stitch.py`.
- `tools/narrate.py`, `tools/render.py`, `tools/title.py`.

---

## Primitive spec envelope

Every clip's `visuals` field has this shape:

```json
{
  "slide_type": "<primitive_name>",
  "data": { ...primitive-specific schema... },
  "annotations": [
    {"at_index": N, "text": "...", "anchor": "data_point|chart|free"}
  ],
  "cue_words": [
    {"at_index": N, "event": "...", "params": {}}
  ],
  "layout": "center|split_left_right|bottom_third|full_bleed",
  "transition_in": "crossfade|cut|wipe_left|fade_black",
  "transition_out": "crossfade_next|cut|fade_black",
  "transition_sound": "<theme_sound>|null"
}
```

**Responsibilities:**
- `data` — ground truth (numbers, series, hierarchy). Primitive-specific schema.
- `annotations` — narrative overlay text that references the data. Decoupled from cue timing.
- `cue_words` — pure timing ("when does what animate"). Event names are primitive-specific; validated against the primitive's `CUE_EVENTS`.

Emphasis is theme-owned. Specs use `"emphasized": true` as a boolean; the theme chooses how to render emphasis (color, pulse, stroke). To change the emphasis treatment, swap themes — don't override per-spec.

---

## Phase 1 primitives (MVP)

### Upgraded from current grammar

**`bar_chart`** (replaces `bar_chart_build`)
```json
"data": {
  "title": "Annual revenue",
  "x_label": "Year",
  "y_label": "USD millions",
  "orientation": "vertical|horizontal",
  "baseline": 0,
  "series": [
    {"label": "2022", "value": 2.1},
    {"label": "2024", "value": 14.3, "emphasized": true}
  ],
  "value_format": "${:.1f}M"
}
```
Renders real axes, auto-ticks, value labels on bars. Emphasized bars pulse via theme treatment.
Cue events: `show_axes`, `show_bar`, `highlight_bar`.

**`counter`** (replaces `counter_sync`)
```json
"data": {
  "from": 0,
  "to": 14300000,
  "format": "${:,.0f}",
  "suffix": "ARR",
  "context_label": "2024 run-rate",
  "duration_s": 2.5,
  "easing": "ease_out_cubic"
}
```
Headline number counts up, context label fades in underneath after settle.
Cue events: `start_count`, `hold`, `reveal_context`.

**`before_after`** (enhanced)
```json
"data": {
  "metric": "Test turnaround time",
  "before": {"value": 72, "label": "Manual", "unit": "hrs"},
  "after":  {"value": 4,  "label": "Automated", "unit": "hrs"},
  "delta_display": "pct_change|ratio|absolute",
  "direction": "lower_is_better|higher_is_better"
}
```
Auto-computes delta; direction controls the polarity of the "good/bad" color treatment (theme-owned).
Cue events: `show_before`, `show_after`, `reveal_delta`.

**`callout`** (renamed from `data_text`)
```json
"data": {
  "primary": "$41",
  "secondary": "prototype BOM",
  "style": "headline|tag|label"
}
```
Clean typographic callout. No pretense of being a chart.
Cue events: `show_primary`, `show_secondary`.

### New data viz primitives

**`line_chart`**
```json
"data": {
  "title": "Yeast fitness over generations",
  "x_label": "Generation",
  "y_label": "Growth rate",
  "series": [
    {"label": "Strain A",
     "points": [[0, 0.42], [5, 0.51], [10, 0.68], [12, 0.74]],
     "emphasized": true},
    {"label": "Strain B",
     "points": [[0, 0.38], [5, 0.41], [10, 0.44], [12, 0.46]]}
  ],
  "highlight_points": [
    {"series": 0, "at": [12, 0.74], "label": "+76% vs baseline"}
  ]
}
```
Real axes with auto-ticks; lines draw left-to-right over clip duration; highlight points flash + annotate at cue timestamps.
Cue events: `draw_axes`, `draw_line`, `highlight_point`, `reveal_annotation`.

**`tree`**
```json
"data": {
  "root": {
    "label": "Ancestral strain",
    "children": [
      {"label": "Variant A", "children": [
        {"label": "A1", "emphasized": true},
        {"label": "A2"}
      ]},
      {"label": "Variant B", "children": [...]}
    ]
  },
  "layout": "radial|horizontal|vertical",
  "node_style": "dot|box|label"
}
```
Auto-laid-out tree (Reingold-Tilford for horizontal/vertical, polar for radial). Nodes appear depth-first with staggered timing.
Cue events: `reveal_root`, `reveal_level`, `highlight_node`.

**`timeline`**
```json
"data": {
  "range": {"start": "2020", "end": "2025"},
  "events": [
    {"at": "2021-Q2", "label": "Pre-seed", "marker": "dot"},
    {"at": "2023-Q1", "label": "First pilot", "marker": "star", "emphasized": true},
    {"at": "2024-Q4", "label": "Series A", "marker": "dot"}
  ],
  "orientation": "horizontal|vertical"
}
```
Axis with tick marks; events appear in temporal order; emphasized events scale + get a connector line to a label card.
Cue events: `draw_axis`, `reveal_event`, `highlight_event`.

### Escape hatch

**`llm_custom`**
```json
"data": {
  "custom_script": "from manim import *\n\nclass Scene_X(Scene):\n    def construct(self):\n        ...",
  "rationale": "Protein folding pathway — no primitive fits",
  "imports": ["numpy"],
  "est_duration_s": 12.4
}
```
Rationale is required for auditing and for phase 3 promotion telemetry. Renderer writes script, runs Manim, retries with traceback feedback on failure.

### Migrated unchanged

`title`, `chapter_card`, `ambient_field`, `svg_reveal`, `photo_organism` — existing behavior preserved, moved into `themes/primitives/*.py` files so the registry auto-discovery pattern is uniform.

### Deprecated (kept for back-compat)

`dot_merge`, `remove_reveal` — parse-evol chemistry-specific. Flagged deprecated in registry descriptions; existing projects still render; new projects should use `llm_custom`.

---

## Phase 2 primitives (future)

Schemas designed in detail in phase 2 spec. Sketches only:

| Primitive | Use case |
|-----------|----------|
| `stacked_area` | composition over time |
| `scatter` | 2D distribution with optional size/color encoding |
| `grouped_bar` | multi-series categorical comparison |
| `pie_donut` | share (summed to 100%) |
| `histogram` | distribution from raw or binned values |
| `sankey` | flow between categorical stages |
| `funnel` | stepped conversion |
| `network` | nodes + edges, force layout |
| `quadrant` | 2×2 positioning |

---

## Data flow

### 1. `viz_extract` — PDF → structured JSON

Called once per project (or when the PDF changes). Passes every page of `spec.pdf` (and `slide_deck.pdf` if present) to Claude vision. For each page, returns:

```json
{
  "page_7": {
    "figure_label": "Figure 3 — Yeast fitness over generations",
    "candidate_primitive": "line_chart",
    "data": { ...primitive-compatible schema... },
    "confidence": 0.84
  }
}
```

Writes to `build/pdf_data.json`. Sidecars a hash of the input PDFs so subsequent runs skip extraction when unchanged (same pattern as the narrate text-hash cache added in this same cycle).

### 2. `direct_prepare` — context for direction

Reads:
- `build/clips.json` (clip text, word_times, pacing)
- `build/pdf_data.json` (extracted viz data)
- `themes/primitives/*.py` SCHEMA and description (auto-assembled)

Returns a single tool result: formatted prompt text describing clip context, primitive schemas, and the extracted PDF data. No vision tokens; `pdf_data.json` is text.

### 3. MCP client emits specs

For each clip, the client follows this fallback chain:

1. **Match against `pdf_data.json`** — if a page's extracted data fits a primitive and matches the clip's narration topic, emit that spec.
2. **Infer from narration** — if no PDF data applies but the narration implies a data shape ("we grew 3× in 18 months"), emit an inferred spec.
3. **Escape to `llm_custom`** — if neither applies, emit a custom script with rationale.
4. **Flag `needs_data`** — if nothing fits and the client can't write a custom script confidently, emit a stub for manual fill.

### 4. `direct_apply` — validate + write

Schema-validates every clip's `visuals` against the primitive's schema. For `llm_custom`, AST-checks the custom_script compiles. On error, writes partial clips.json with error list (same pattern as today).

### 5. Render

`compose.py` walks the DAG per clip. Dispatcher in `biopunk.render_choreography` looks up the primitive module and calls `primitive.render(clip, duration, images_dir, theme)`. The primitive returns Manim code; `manim_fused` compiles and renders.

For `llm_custom` clips, the DAG routes to `renderers/manim_llm_custom.py` with the compile-retry loop.

---

## Schema validation

Each primitive module owns its schema. Lightweight approach using plain dict/list checks or Pydantic models — TBD during implementation. Whatever approach, these are the invariants:

- Required fields present with correct type.
- Enum fields (orientation, style, layout) are in allowed set.
- Numeric fields in valid range.
- `cue_words.event` ∈ `CUE_EVENTS` for the primitive.
- `cue_words.at_index` < len(word_times).
- `annotations.at_index` < len(word_times).

---

## Caching

All existing caching patterns stay and extend:

- `viz_extract` — sidecar `.pdfhash` skips re-extraction when source PDFs unchanged.
- `narrate` — sidecar `.wav.txthash` skips re-synthesis when text + voice config unchanged.
- `compose` per-node content hashing — DAG nodes skip re-render when `clip.text`, `clip.word_times`, `clip.timing`, `clip.visuals` all unchanged.
- `llm_custom` content hash includes the full custom_script, so script edits invalidate the render cache.

---

## Acceptance criteria

**Phase 1 MVP ships when:**

1. `parse-evols-yeast` renders end-to-end on the new grammar.
2. ≥60% of data-bearing clips use a typed primitive (not `llm_custom`).
3. Output visibly grounds data in real numbers — spot-check 5 clips, each shows axes/units/values that can be traced back to `pdf_data.json`.
4. Existing `perilux` project (legacy path) still renders unchanged.
5. Schema validation rejects malformed specs before render, with errors that point at the failing clip + field.
6. `llm_custom` compile-retry loop recovers from at least one realistic Manim syntax error without manual intervention.

---

## Risks

**Vision extraction quality.** Claude may misread chart axis values, especially for unconventional or low-resolution figures.
*Mitigation:* `pdf_data.json` is a reviewable artifact. User edits before `direct_prepare` runs. Confidence score per page surfaces uncertain reads.

**`llm_custom` runaway retries.** Compile-retry loop could burn tokens on pathological scripts.
*Mitigation:* Hard cap at 3 retries. Failure returns a clear error; user edits the custom_script manually.

**Schema evolution breakage.** Once a schema is authored into `clips.json` across multiple projects, changing it breaks old projects.
*Mitigation:* Schemas are versioned via the git history of primitive files. Phase 1 ships with a freeze; phase 2 additions must be purely additive.

**Biopunk refactor regression.** Moving 500 lines of method-map code into new files risks breaking existing rendering.
*Mitigation:* Rendered-output byte-for-byte comparison against a saved baseline for each existing primitive during refactor. No intended behavior change for content primitives.

---

## Open items deferred to implementation plan

- Pydantic vs. plain dict validation
- `pdf_data.json` schema (what exactly does each page entry look like beyond the example above)
- `viz_extract` retry/rate-limit behavior on Claude API errors
- Whether to persist `llm_custom` compile errors to a debug log for phase 3 promotion analysis
- Exact tree layout algorithm for `tree` primitive (Reingold-Tilford vs. Walker's)
