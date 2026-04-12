# Sub-Clip Architecture Design

> Refactor the docu-gen MCP server from chapter-level to clip-level granularity.
> Clips are the atomic unit of narration, visuals, and timing.

---

## Problem

The current pipeline operates on whole chapters. This causes:

1. **Emotion is flat per chapter.** One exaggeration value for 100+ seconds of narration. Punchlines get the same delivery as exposition.
2. **Visual timing is brittle.** Each chapter is one Manim scene with hardcoded `self.wait(N)` calls that drift from actual narration. Front-loaded animations leave dead static time.
3. **Iteration is slow.** Changing one visual moment means re-rendering the entire chapter (60-100s of Manim).
4. **No pacing control.** Every beat gets the same buffer. Rapid-fire data sequences and dramatic pauses both get identical treatment.

## Solution

Introduce **clips** as the atomic unit. A clip is one narration segment (1-3 sentences) paired with one visual treatment and one emotion setting. Chapters become ordered containers of clips.

New pipeline: `init -> plan -> split -> narrate -> render -> score -> stitch`

---

## Data Model

### plan.json (unchanged)

Produced by `plan`. Chapters with full narration text and visual references.

```json
{
  "title": "Project Title",
  "chapters": [
    {
      "id": "ch1_paper",
      "title": "The Paper",
      "narration": "Full chapter narration text...",
      "visuals": {
        "manim": "Description of visual treatment...",
        "existing_svg": ["01-phase-a-survival.svg"],
        "source_images": ["img_yeast_micro"],
        "new_svg": []
      }
    }
  ]
}
```

### clips.json (new, produced by `split`)

The working format for all downstream tools.

```json
{
  "title": "Project Title",
  "theme": "biopunk",
  "chapters": [
    {
      "id": "ch1_paper",
      "title": "The Paper",
      "clips": [
        {
          "clip_id": "ch1_paper_01",
          "text": "It starts with a paper.",
          "exaggeration": 0.25,
          "emotion_tag": "neutral",
          "pacing": "normal",
          "visuals": {
            "type": "chapter_card",
            "assets": [],
            "direction": ""
          }
        },
        {
          "clip_id": "ch1_paper_02",
          "text": "In 2017, Sarnoski, Liu, and Acar published a method for screening yeast replicative lifespan. They called it High-Life -- which, honestly, is a better name than anything we came up with.",
          "exaggeration": 0.35,
          "emotion_tag": "wry",
          "pacing": "normal",
          "visuals": {
            "type": "image_reveal",
            "assets": ["img_paper_header.svg"],
            "direction": "Fade in paper header, hold center, slow zoom 1.04x"
          }
        },
        {
          "clip_id": "ch1_paper_03",
          "text": "They tracked how many times each yeast cell divided before it died, and out of 2,000 compounds tested, they found two that worked. Two.",
          "exaggeration": 0.30,
          "emotion_tag": "building",
          "pacing": "breathe",
          "visuals": {
            "type": "image_reveal",
            "assets": ["01-phase-a-survival.svg"],
            "direction": "Survival curves draw themselves, treatment groups separate"
          }
        }
      ]
    }
  ]
}
```

### Clip fields

| Field | Type | Description |
|-------|------|-------------|
| `clip_id` | string | `{chapter_id}_{nn}` — unique, ordered |
| `text` | string | Narration text for this clip (1-3 sentences) |
| `exaggeration` | float | Chatterbox emotion intensity 0.0-1.0, auto-tagged, overridable |
| `emotion_tag` | string | Human-readable label: neutral, wry, deadpan, dramatic, building, punchline |
| `pacing` | string | `tight` / `normal` / `breathe` — controls post-narration buffer |
| `visuals.type` | string | Renderer dispatch: blank, chapter_card, image_reveal, data_reveal, animation |
| `visuals.assets` | list | File references (SVGs, images) from the project images/ directory |
| `visuals.direction` | string | Free-text creative direction for the renderer. Empty = theme default. |

### Pacing values

| Value | Buffer after narration | Use case |
|-------|----------------------|----------|
| `tight` | 0.5s | Rapid-fire lists, data sequences |
| `normal` | 1.5s | Default. Visual lands, momentum continues. |
| `breathe` | 3.5s | Punchlines, dramatic reveals, let silence do the work |

### Visual types

| Type | Behavior |
|------|----------|
| `blank` | Theme's idle state: background elements + ambient motion. No assets. |
| `chapter_card` | Chapter number + title with theme treatment (throb, glow, etc.) |
| `image_reveal` | Ken Burns motion on an image or SVG. Direction controls zoom/pan. |
| `data_reveal` | Text, numbers, stats appearing on screen. Direction describes what/how. |
| `animation` | Custom Manim sequence. Direction is the choreography description. |

---

## Pipeline: 7 Tools

### 1. `init` (new)

Creates a new project directory and selects a theme.

**Input:** project name
**Output:** project directory with config.yaml, images/, prompt.txt

**Behavior:**
- Creates `projects/{name}/` with subdirectories: `images/`, `build/`
- Lists available themes from `src/docugen/themes/`
- Writes `config.yaml` with selected theme and sensible defaults
- Returns project path and summary

### 2. `plan` (unchanged)

Extracts PDF text and generates chapter plan via AI.

**Input:** project_path
**Output:** `build/plan.json` with chapters, narration, visual references

### 3. `split` (new)

Splits chapters into clips with emotion tagging and pacing assignment.

**Input:** project_path (reads `build/plan.json`)
**Output:** `build/clips.json`

**Split algorithm:**

1. Parse each chapter's narration into sentences.
   - Use spacy sentence segmentation if available.
   - Fallback: split on `. `, `? `, `! ` with heuristics for abbreviations.

2. Walk sentences, accumulating into a clip. Start a new clip when:
   - The next sentence references a different visual asset than the current clip.
   - The current clip exceeds 35 words (~15s of narration).
   - The chapter's first clip should be a `chapter_card` type (just the title, no narration, or the first short sentence).

3. Keep together as one clip:
   - A short punchline sentence immediately following a long setup (e.g., "Two." after a complex sentence).
   - Sentence pairs where the second starts with a conjunction or continuation word.

4. Assign `visuals` per clip:
   - Map assets from plan.json's `visuals` fields to clips based on which sentences reference them (positional — first assets go to earlier clips).
   - Clips with no mapped asset get `type: "blank"`.
   - First clip of each chapter gets `type: "chapter_card"`.
   - `direction` populated from plan.json's `visuals.manim` field when present, split proportionally across clips. Empty for blank/chapter_card types.

5. Auto-tag emotion:
   - **Snark markers:** "honestly", "apparently", "you're welcome", "by the way", rhetorical questions → bump exaggeration +0.15, tag as `wry` or `punchline`.
   - **Short-after-long pattern:** sentence < 5 words following sentence > 25 words → `punchline`, bump +0.10.
   - **Dramatic markers:** numbers with "percent", superlatives, "the answer is" → `dramatic`, bump +0.10.
   - **Deadpan:** chapter-level exaggeration < 0.25 and no snark markers → `deadpan`.
   - **Base:** inherit chapter-level exaggeration from plan.json, apply bumps on top (capped at 0.8).

6. Auto-assign pacing:
   - Short sentence (< 8 words) at end of a conceptual beat → `breathe`.
   - Sentences in a list cadence (3+ sequential short items) → `tight`.
   - Rhetorical question → `breathe`.
   - Default → `normal`.

7. `clips.json` is human-editable. Users can adjust exaggeration, pacing, direction, or clip boundaries before running narrate.

### 4. `narrate` (refactored)

Generates one WAV per clip.

**Input:** project_path (reads `build/clips.json`, `config.yaml`)
**Output:** `build/narration/{clip_id}.wav` for each clip

**Behavior:**
- Supports both `openai` and `chatterbox` engines (existing).
- For chatterbox: each clip gets its own `exaggeration` value from clips.json.
- Post-FX (ring mod, formant shift) applied per clip when configured.
- Model loaded once, reused across all clips (existing lazy-load pattern).
- Skips clips that already have a WAV (for incremental re-generation).
- No duration estimation or speed adjustment needed — clip text is short enough that overrun isn't an issue.

### 5. `render` (refactored)

Generates one MP4 per clip.

**Input:** project_path (reads `build/clips.json`, clip WAV durations)
**Output:** `build/clips/{clip_id}.mp4` for each clip

**Behavior:**
- Reads each clip's WAV to get actual narration duration.
- Adds pacing buffer: tight +0.5s, normal +1.5s, breathe +3.5s.
- Loads the project's theme module.
- Dispatches on `visuals.type`:
  - `blank` → theme's `idle_scene(duration)`
  - `chapter_card` → theme's `chapter_card(num, title, duration)`
  - `image_reveal` → theme's `image_reveal(assets, direction, duration)`
  - `data_reveal` → theme's `data_reveal(direction, duration)`
  - `animation` → theme's `custom_animation(direction, duration, assets)`
- Each scene includes the theme's ambient background (floating dots, grid, etc.) for visual continuity across clips.
- Skips clips that already have an MP4 (incremental).

### 6. `score` (new, extracted from stitch)

Generates the drone score as a standalone step.

**Input:** project_path (reads `build/clips.json`, clip WAV durations)
**Output:** `build/score.wav`

**Behavior:**
- Builds a timeline from clip durations, grouped by chapter.
- Per-chapter drone layers (from score.py, existing).
- Transition sounds at chapter boundaries (from score.py, existing).
- Global fade in/out.
- Standalone so the score can be regenerated without re-rendering visuals.

### 7. `stitch` (simplified)

Assembles everything into the final video.

**Input:** project_path (reads `build/clips.json`)
**Output:** `build/final.mp4`

**Behavior:**
- Concatenates `build/clips/{clip_id}.mp4` in order (ffmpeg concat).
- Builds voice track from `build/narration/{clip_id}.wav` placed at correct offsets.
- Loads `build/score.wav`.
- Mixes voice + score with voice-activated ducking.
- Muxes audio onto concatenated video.
- No generation logic — pure assembly.

---

## Theme Modules

### Directory structure

```
src/docugen/themes/
  __init__.py       — registry: list_themes(), load_theme(name)
  base.py           — ThemeBase abstract class
  biopunk.py        — current biopunk Imperial theme
```

### ThemeBase interface

```python
class ThemeBase:
    name: str                          # "biopunk"
    palette: dict[str, str]            # color name -> hex
    font: str                          # "Courier"

    def manim_header(self) -> str:
        """Return Manim preamble code: imports, colors, helper functions."""

    def idle_scene(self, duration: float) -> str:
        """Return Manim script for a blank themed slide."""

    def chapter_card(self, num: str, title: str, duration: float) -> str:
        """Return Manim script for a chapter title card."""

    def image_reveal(self, assets: list[str], direction: str,
                     duration: float, images_dir: str) -> str:
        """Return Manim script for image/SVG reveal with Ken Burns."""

    def data_reveal(self, direction: str, duration: float) -> str:
        """Return Manim script for text/data appearing on screen."""

    def custom_animation(self, direction: str, duration: float,
                         assets: list[str], images_dir: str) -> str:
        """Return Manim script for a custom animation sequence."""

    def transition_sounds(self) -> dict[str, callable]:
        """Return dict of chapter_id -> audio generator function."""

    def chapter_layers(self) -> dict[str, callable]:
        """Return dict of chapter_id -> drone layer generator function."""
```

### Theme selection

- `config.yaml` has `theme: biopunk` field.
- `init` tool lists available themes and writes the choice.
- `render` and `score` load the theme module at runtime.
- New themes: add a Python file to `themes/`, subclass `ThemeBase`.

---

## File Layout After Refactor

```
src/docugen/
  server.py              — MCP server with 7 tools
  config.py              — config loader (add theme field to defaults)
  split.py               — split algorithm (new)
  themes/
    __init__.py           — registry
    base.py               — ThemeBase
    biopunk.py            — extracted from theme.py + scenes.py + score.py
  tools/
    init.py               — project setup (new)
    plan.py               — unchanged
    narrate.py             — refactored: per-clip generation
    render.py              — refactored: per-clip, theme-dispatched
    score.py               — extracted from stitch (new tool)
    stitch.py              — simplified: assembly only
```

### Files to delete after refactor
- `src/docugen/theme.py` — replaced by `themes/biopunk.py`
- `src/docugen/scenes.py` — replaced by theme's scene methods
- `src/docugen/score.py` — moved to `themes/biopunk.py` (score layers are theme-specific)
- `src/docugen/drone.py` — base drone logic moves to `tools/score.py`, chapter-specific layers to theme

---

## Config Changes

### config.yaml defaults (updated)

```yaml
theme: biopunk            # new — theme module name
voice:
  engine: openai
  model: tts-1-hd
  voice: echo
video:
  resolution: 1080p
  fps: 60
drone:
  cutoff_hz: 400
  duck_db: -18
  rt60: 1.5
```

Theme-specific config (colors, transition sounds, drone layers) lives in the theme module, not in config.yaml. Config.yaml is for project-level overrides (voice, resolution, drone tuning).

---

## Build Directory Structure

```
build/
  plan.json               — chapter-level plan (from plan tool)
  clips.json              — clip-level breakdown (from split tool)
  narration/
    ch1_paper_01.wav       — per-clip narration
    ch1_paper_02.wav
    ...
  clips/
    ch1_paper_01.mp4       — per-clip video
    ch1_paper_02.mp4
    ...
  score.wav                — full drone score
  final.mp4                — assembled output
```

---

## Incremental Re-generation

A key benefit of clip-level granularity: you can re-generate individual clips without re-doing everything.

- Change a clip's `direction` in clips.json → re-render just that clip's MP4, re-stitch.
- Change a clip's `exaggeration` → re-narrate just that clip's WAV, re-render (duration may change), re-stitch.
- Change a clip's `text` → re-narrate, re-render, re-stitch.
- Change the score → re-score, re-stitch. No re-render needed.

Each tool skips files that already exist. To force re-generation, delete the specific file.

---

## Testing Strategy

- **split.py:** Unit tests with known narration text. Assert correct clip boundaries, emotion tags, pacing. No external dependencies.
- **narrate.py:** Existing tests adapted — mock Chatterbox/OpenAI, verify per-clip WAV generation.
- **render.py:** Test Manim script generation (string output), not actual rendering. Verify theme dispatch, duration calculation.
- **score.py:** Test timeline construction and audio output shape. Existing drone tests adapt.
- **stitch.py:** Test concat file generation, audio mixing math. Mock ffmpeg calls.
- **themes/biopunk.py:** Test that each method returns valid Manim script strings.

---

## Migration Path

1. Build the new modules alongside existing code.
2. The parse-evols-yeast project's existing `build/` artifacts remain valid — stitch can still assemble them.
3. Once the new pipeline is working, update server.py to expose the 7 tools.
4. Delete old files (theme.py, scenes.py, score.py, drone.py).
5. Existing projects can be upgraded by running `split` on their plan.json.

---

## Out of Scope

- AI-generated visual direction (the `direction` field is human-authored or template-based, not LLM-generated at split time).
- Real-time preview of individual clips.
- Multi-language narration.
- Video export formats beyond MP4.
