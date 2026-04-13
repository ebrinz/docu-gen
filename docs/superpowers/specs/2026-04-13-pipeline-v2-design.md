# Pipeline v2: Creative Director + Bespoke Rendering

**Date:** 2026-04-13
**Status:** Design
**Scope:** Replace template-based choreography with LLM-driven creative direction, word-time-synced rendering, and bespoke Manim scene builders.

---

## 1. Problem

The current visual pipeline produces repetitive output. Ten animation primitives assigned by regex produce identical-looking clips regardless of content. The renderer ignores word-level timestamps. Assets are distributed via FIFO queue instead of mapped to narration content. Pacing uses hardcoded buffers instead of actual audio timing. Clips are hard-cut with no transitions.

## 2. New Pipeline

```
init → plan → split → narrate → align → direct → render → score → stitch
```

`direct` replaces `choreograph`. Everything else keeps its current interface with internal improvements.

## 3. The `direct` Tool

### 3.1 Overview

A new MCP tool that makes a single Claude API call to assign unambiguous visual instructions to every clip. Replaces the regex-based `choreograph` tool entirely.

### 3.2 Inputs

The LLM prompt receives:
- Production plan `visuals.manim` descriptions per chapter
- Each clip's narration text + `word_times` from `clips.json`
- Available slide type registry (section 5)
- Available image assets (`ls images/`)
- Optional `creative_notes` parameter (free-text creative direction from user)

### 3.3 Output Per Clip

Written back to `clips.json` under each clip's `visuals` key:

```json
{
  "slide_type": "counter_sync",
  "assets": ["07-source-composition.svg"],
  "cue_words": [
    {
      "word": "billion",
      "at_index": 8,
      "event": "start_counter",
      "params": {"to": 420, "color": "gold", "label": "dollars"}
    }
  ],
  "layout": "center",
  "transition_in": "crossfade",
  "transition_out": "crossfade_next",
  "transition_sound": "imperial_chime"
}
```

### 3.4 Required Fields

Every clip must have ALL of these after `direct` runs:

| Field | Type | What it answers |
|-------|------|----------------|
| `slide_type` | string | Which scene builder renders this clip |
| `assets` | string[] | Specific filenames from `images/` (can be empty) |
| `cue_words` | object[] | Word-index-to-visual-event mappings |
| `layout` | string | Element positioning: `center`, `split_left_right`, `bottom_third`, `full_bleed` |
| `transition_in` | string | `crossfade`, `cut`, `wipe_left`, `fade_black` |
| `transition_out` | string | `fade_black`, `crossfade_next`, `cut` |
| `transition_sound` | string or null | One of the 8 theme transition sounds, or null |

### 3.5 Validation Pass

After the LLM output is parsed, a validation pass runs:
- Every clip has all 7 required fields
- Every referenced asset exists in `images/`
- Every `at_index` in cue_words is within the clip's `word_times` bounds
- Every `slide_type` is in the registered slide type set
- Every `event` is valid for that slide type

If validation fails, the tool halts with a clear error listing which clips have which problems. The user fixes them in `clips.json` and re-runs `direct` or proceeds to `render`.

### 3.6 API

```python
@mcp.tool()
def direct(project_path: str, creative_notes: str = "") -> str:
    """Assign visual direction to every clip using AI.

    Reads production plan visual descriptions, clips.json with word_times,
    and available assets. Makes one Claude API call to assign slide types,
    asset mappings, cue words, layouts, and transitions per clip.

    Replaces the old choreograph tool.

    Args:
        project_path: Path to project directory.
        creative_notes: Optional free-text creative direction.
    """
```

## 4. Timing Model

### 4.1 Source of Truth

All timing derives from WAV files and word_times. No hardcoded buffers.

### 4.2 Per-Clip Timing

Computed by `direct` and written to `clips.json`:

```json
{
  "timing": {
    "wav_duration": 4.82,
    "speech_start": 0.0,
    "speech_end": 4.16,
    "trailing_silence": 0.66,
    "pacing_pad": 0.84,
    "clip_duration": 5.66,
    "chapter_offset": 12.34
  }
}
```

- `wav_duration`: measured length of the clip's WAV file
- `speech_start`: first word's `start` from word_times
- `speech_end`: last word's `end` from word_times
- `trailing_silence`: `wav_duration - speech_end`
- `pacing_pad`: `max(0, target_pad - trailing_silence)` where target_pad = `{"tight": 0.5, "normal": 1.5, "breathe": 3.0}`
- `clip_duration`: `wav_duration + pacing_pad` — the actual render duration
- `chapter_offset`: cumulative from chapter start. Clip N offset = sum of clip_duration for clips 0..N-1

For clips without narration (chapter cards): `duration_source: "fixed:3.0"`, chapter_offset still computed.

### 4.3 Downstream Consumers

- **render**: uses `clip_duration` as Manim scene length. Reads `word_times` + `cue_words` to fire visual events at exact timestamps.
- **score**: uses `chapter_offset` for chapter boundary times and transition sound placement.
- **stitch**: uses `chapter_offset` to place narration WAVs in the final audio mix. Reads `transition_in`/`transition_out` for ffmpeg xfade filters.

## 5. Slide Types (Scene Builders)

### 5.1 Registry

| Slide Type | Description | Key cue_word events |
|-----------|-------------|-------------------|
| `title` | Title + subtitle with configurable reveal style | `reveal_title`, `reveal_subtitle` |
| `chapter_card` | Chapter number + title, imperial border draws in | `reveal_number`, `reveal_title` |
| `svg_reveal` | SVG asset fades/draws in, Ken Burns drift, labels | `show_asset`, `highlight_region`, `show_label` |
| `photo_organism` | Photo inset with HUD border, animated pointer labels | `show_photo`, `show_structure`, `show_name`, `show_note` |
| `counter_sync` | Number animates 0 to target, keyed to narration word | `start_count`, `hold` |
| `bar_chart_build` | Horizontal bars grow in sequence, synced to list | `show_bar` (one per item) |
| `before_after` | Side-by-side comparison with morphing values | `show_before`, `show_after`, `morph` |
| `dot_merge` | Two compound dots approach and merge | `show_dot1`, `show_dot2`, `merge` |
| `remove_reveal` | One compound fades, another emerges | `remove`, `reveal` |
| `data_text` | Key text/numbers on screen synced to narration | `show_text` |
| `ambient_field` | Particle field + theme bg, no foreground content | (none) |

### 5.2 Title Slide

**Font:** Rajdhani (downloaded as TTF from Google Fonts, registered with Manim).

**Reveal styles** (set via `params.reveal_style`):
- `particle` (default): Drifting particle field, particles rush inward and assemble into title letterforms. Subtitle materializes from horizontal scanline.
- `glitch`: Title appears instantly with RGB channel offset + scanline distortion, then "locks in" over 1-2s. Subtitle types character by character.
- `trace`: Letter strokes draw their own paths, then fill with gold-to-cyan gradient sweep.
- `typewriter`: Characters appear one at a time with cursor blink.

**API:**
```python
@mcp.tool()
def title(project_path: str, title_text: str = "",
          subtitle_text: str = "", reveal_style: str = "particle") -> str:
    """Generate a title card video clip.

    Uses Rajdhani font with configurable reveal animation.
    Reads project config for theme colors and resolution.

    Args:
        project_path: Path to project directory.
        title_text: Main title (defaults to production plan title).
        subtitle_text: Subtitle (defaults to production plan subtitle).
        reveal_style: Animation style — particle, glitch, trace, typewriter.
    """
```

Renders directly to `build/clips/intro_01.mp4`.

### 5.3 Photo Organism (HUD Treatment)

Photos get a tactical display aesthetic:
- Photo rendered as inset with imperial border frame (corner brackets, thin gold rule)
- Animated pointer line extends from photo to a label callout box
- Label box contains: compound name (bold), source organism, one-line note
- Text scans in or types in (not instant)
- Multiple pointers can appear sequentially, keyed to `cue_words`
- Pointer lines use the theme accent color for that organism's source category

## 6. Narrate Improvements

### 6.1 Number-to-Words (done)

Already implemented in `src/docugen/numberwords.py`. Converts all numeric symbols to natural English before TTS. Handles dollars, percentages, comma-separated numbers, decimals, years. Preserves compound names (PI-103, Rb1, K-2SO).

### 6.2 Short Clip Consolidation (Chatterbox)

Chatterbox chokes on short clips (<=6 words) with high exaggeration (>=0.3). Fix:

1. **Detect** short+hot clips before TTS generation
2. **Merge** the short clip's text with its preceding neighbor (the setup to the punchline)
3. **Generate** one WAV with the combined text at the lower exaggeration of the two
4. **Align** the combined WAV with Whisper to get word boundaries
5. **Split** the WAV at the sentence boundary using word_times
6. **Write** two separate clip WAVs — downstream tools see normal individual clips

Only applies when `engine: chatterbox`. OpenAI TTS handles short clips fine.

### 6.3 Snarky Narrator Easter Egg

When `config.yaml` has `engine: chatterbox` and `ref_audio` points to the default robot voice (`assets/robo.flac` or `assets/K-2SO.wav`), the narrate tool runs a light LLM text transform before TTS:

- Inserts dry parenthetical asides at dramatic pauses or big numbers
- Adds deadpan commentary on rhetorical questions
- One or two injections per chapter, not every sentence
- The transform is a small Claude API call that takes narration text and the K-2SO voice character brief
- Only activates for robot voice — human-cloned voices get text as-is

The snarky text is written back to `clips.json` as `narration_text_spoken` so you can review what actually got sent to TTS vs. the original `text`.

## 7. Stitch Improvements

### 7.1 Cross-fade Transitions

Replace hard-cut ffmpeg concatenation with xfade filters between clips:
- Read `transition_in` / `transition_out` per clip from clips.json
- Apply ffmpeg xfade filter with appropriate duration (0.3s for cuts, 0.8s for crossfades, 1.2s for fade_black)
- Transition sounds from the score are already timed to chapter_offset boundaries

### 7.2 WAV-Derived Audio Placement

Replace the accumulate-with-buffers audio placement in stitch with chapter_offset values from the timing model. Each narration WAV is placed at its exact `chapter_offset` position in the final mix.

## 8. Score Improvements

The score tool reads `chapter_offset` from the timing model for accurate chapter boundary times. Transition sounds (`imperial_chime`, `dark_swell`, etc.) are placed at the exact boundary timestamps rather than estimated positions.

## 9. Files Changed

| File | Change |
|------|--------|
| `src/docugen/server.py` | Replace `choreograph` tool with `direct` and `title` tools |
| `src/docugen/direct.py` | New — LLM creative director + validation + timing computation |
| `src/docugen/numberwords.py` | Already built — number-to-words conversion |
| `src/docugen/tools/narrate.py` | Short clip consolidation, snarky easter egg, numbers_to_words (done) |
| `src/docugen/tools/render.py` | Dispatch to slide type builders, consume word_times + cue_words |
| `src/docugen/tools/score.py` | Read chapter_offset from timing model |
| `src/docugen/tools/stitch.py` | xfade transitions, WAV-derived audio placement |
| `src/docugen/themes/biopunk.py` | New scene builders per slide type, HUD photo treatment |
| `src/docugen/choreographer.py` | Deleted — replaced by direct.py |
| `assets/fonts/Rajdhani-*.ttf` | New — Google Fonts download for title rendering |

## 10. What's NOT in Scope

- Web-based CSS/JS renderer — staying all-Manim for now
- LLM-generated Manim per clip (freeform code gen) — too unpredictable. LLM picks from the slide type registry, doesn't write Manim.
- Score synced to individual word cues — score stays chapter-level. Only the visual renderer consumes word_times.
- Extracting compounds/organisms from production plan into config — keep hardcoded for parse-evol, generalize in a future pass.
