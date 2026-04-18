# Audio-First Pipeline & Storyboard Gate

**Date:** 2026-04-18
**Status:** Draft — awaiting review
**Scope:** Restructure render pipeline around audio-bound clips; add pre-render storyboard review; wire title card; diversify chapter openers; ban short-emotive narration at the plan stage.

## Problem

Four issues surfaced in the perilux run:

1. **No title slide.** `title` MCP tool exists but isn't invoked by any default chain; final video has no opening card.
2. **Duplicated chapter openers.** plan.json gave three chapters the same `scene_type: infographic`, and `direct_apply` reasoned on each in isolation, producing near-identical openers.
3. **Short emotive clips error in Chatterbox.** Short high-exaggeration lines are a known Chatterbox failure mode; current `narrate.py` consolidation logic does not reliably catch them.
4. **Narration drifts from visual track.** Manim decides its own scene duration; it can overrun or underrun `clip_duration` from `timing.py`. Small per-clip drifts accumulate into audible/visible misalignment over a full video.

Root diagnosis: visuals are the timing authority today (Manim renders, we trust its output duration). Audio should be authoritative — every other element bends to it.

## Design

### Pipeline shape

```
init
  → plan_prepare → plan_apply
  → split
  → narrate
  → base_clips            ← NEW: audio-bound black MP4 per clip
  → storyboard_preview    ← NEW: review gate, optional but recommended
  → viz_extract
  → direct_prepare → direct_apply
  → spot
  → render                  (Manim with duration budget)
  → composite             ← NEW: overlay Manim on base, force duration
  → score
  → stitch                  (auto-invokes title if build/title.mp4 missing)
```

Three new MCP tools (`base_clips`, `storyboard_preview`, `composite`), one auto-invocation (title inside stitch), and validator logic inside `plan_apply` and `direct_apply`.

### 1. Audio-bound rendering

**Contract:** every `clips/<id>.mp4` emitted has duration exactly equal to `clip.timing.clip_duration` (± 1 frame). No drift can escape the composite stage.

**`base_clips` tool:**
- Input: `clips.json` (after narrate + timing).
- Output: `build/base/<clip_id>.mp4` per clip — silent black H.264 at the project's resolution/fps (read from `config.yaml`), duration = `clip.timing.clip_duration`.
- Implementation: `ffmpeg -f lavfi -i color=c=black:s=WxH:r=FPS -t DUR -c:v libx264 -pix_fmt yuv420p -an`.

**Manim render changes:**
- Scene called with `total_duration=clip_duration`. Scene builders use `self.wait(total_duration - elapsed)` at the end to pad; trim logic (`self.mobjects` fadeout) if animations overrun.
- Manim output no longer considered final — it's an overlay.

**`composite` tool:**
- Input: `build/base/<id>.mp4`, `build/frames/<id>.mp4` (Manim), `build/narration/<id>.wav`.
- Output: `build/clips/<id>.mp4`.
- ffmpeg command:
  ```
  ffmpeg -i base.mp4 -i manim.mp4 -i narration.wav \
         -filter_complex "[0:v][1:v]overlay=shortest=0[v]" \
         -map "[v]" -map 2:a \
         -t {clip_duration} -c:v libx264 -c:a aac \
         clips/<id>.mp4
  ```
- Silent clips: skip audio input, emit silent track so concat is uniform.
- Post-write assertion: `ffprobe(out).duration` within 1/fps of `clip_duration`; raise if not.

### 2. Storyboard preview gate

Optional but recommended stage between narrate and direct. Lets the user validate timing, pacing, silent-card durations, and content alignment *before* spending compute on direction + Manim.

**`storyboard_preview` tool:**
- Input: `clips.json`, `build/base/*.mp4`, `build/narration/*.wav`.
- Output: `build/storyboard.mp4`.
- Per clip, burn the following overlay onto the base clip:
  - **Top line:** `CLIP NN / <clip_id>` (large, monospace).
  - **Middle tag:** content descriptor — `<scene_type> · <diagram_type or primitive> · <assets>`. Pulled from clips.json fields.
  - **Bottom subtitle:** narration text if present; blank if silent card.
- Mux narration wav (or silence for silent clips).
- Concat all into `storyboard.mp4`.

The user watches end-to-end, edits `clips.json` / `plan.json` if timing feels off, and reruns from narrate. Only when storyboard feels right do they run viz_extract → direct → render.

### 3. Title card auto-wiring

- `stitch` checks for `build/title.mp4` at start.
- If missing, invokes `title` tool with `project.title` from `plan.json` and default style from `config.yaml` (or `audiowide_particles` fallback per the existing title preference memory).
- Prepends `title.mp4` to the concat list.
- User can still pre-generate with `title` directly to customize; `stitch` only fills the gap.

### 4. Chapter opener variety

Root cause: `direct_prepare` builds per-clip context with no knowledge of sibling chapters' chosen primitives. LLM defaults to whatever is canonical for that scene_type.

**Fix:**
- `direct_prepare` adds a `prior_directions` field to each clip's context: a compact summary of preceding clips' chosen primitive *and* opening reveal style (e.g., `[{clip_id: "intro", primitive: "banner_intro", reveal: "fade_in"}, {clip_id: "ch1", primitive: "open_loop_mouth", reveal: "center_zoom"}]`). The reveal dimension matters because the perilux case had different `diagram_type` per chapter but visually similar openers — the duplication lived in reveal/framing, not primitive identity.
- Prompt instructs the director to prefer variety when multiple primitives or reveal styles would serve the content.
- `direct_apply` validator: warn (not fail) if three consecutive clips share either the same primitive or the same reveal style. User can accept or rerun with a variety bias.

### 5. Short-emotive ban at plan stage

Test-sweep conclusion: long emotive renders beautifully in Chatterbox; short emotive fails. Move enforcement upstream — reject narration that can't possibly render well, rather than consolidate afterward.

**Validator in `plan_apply`** (and `split` for clip-level):
- For each clip: compute `word_count = len(narration.split())` and resolve `exaggeration` (clip override, or chapter default).
- **Ban condition (proposed, confirm in review):** `word_count ≤ 8 AND exaggeration ≥ 0.30`. Chosen to match the first two tiers of the existing Chatterbox clamping memory (≤4w/0.30, ≤8w/0.40) as a hard floor.
- On violation: `plan_apply` raises with the offending clip id, word count, exaggeration, and a suggestion: "lengthen narration" or "drop exaggeration below 0.30".
- **narrate.py existing consolidation** (`_detect_short_hot_clips`, `_plan_consolidation`) stays as a safety net — it should never fire once the upstream validator is in place, but provides defense-in-depth if a hand-edited clips.json slips through.

## Data flow

```
plan.json          ──▶ plan_apply [SHORT-EMOTIVE BAN]
  │
  ▼
clips.json         ──▶ split → narrate
  │                     │
  │                     └─▶ narration/*.wav + word_times
  │
  ▼
timing.py fills clip.timing.clip_duration
  │
  ▼
base_clips ──▶ build/base/*.mp4  (silent black at clip_duration)
  │
  ▼
storyboard_preview ──▶ build/storyboard.mp4  [REVIEW GATE]
  │
  ▼  (user approves)
viz_extract → direct_prepare [PRIOR_DIRECTIONS] → direct_apply [VARIETY WARN]
  │
  ▼
spot → render (Manim with total_duration hint) ──▶ build/frames/*.mp4
  │
  ▼
composite ──▶ build/clips/*.mp4  (base + manim + audio, duration-forced)
  │
  ▼
score → stitch (auto-title) ──▶ final.mp4
```

## Error handling

- **`base_clips`:** per-clip ffmpeg failure → raise with clip id and ffmpeg stderr; do not continue partial.
- **`composite`:** ffprobe duration mismatch → raise loudly with expected vs actual; fix the offending stage, never silently accept drift.
- **`plan_apply` ban:** collect all violations, raise a single error listing every offending clip — avoid one-at-a-time whack-a-mole.
- **`direct_apply` variety:** warn only; not a failure.
- **`stitch` title auto-gen:** if `title` tool errors, fail stitch with the underlying error; user can manually disable by pre-placing an empty `build/title.mp4.skip` marker file.

## Testing

- **Unit:** `compute_clip_timing` output is unchanged (base_clips is a pure derivation of existing field).
- **Integration:** `base_clips` → ffprobe durations match `clip_duration` for every clip.
- **Integration:** `composite` duration assertion holds across a small fixture project (≥3 clips with varied durations).
- **Regression:** perilux project runs end-to-end; final.mp4 duration = sum of `clip_duration` + title card.
- **Validator:** `plan_apply` rejects a fixture with short+hot clip; `plan_apply` accepts the same fixture with exaggeration lowered.
- **Storyboard:** manual review — storyboard.mp4 plays, overlay text is legible, silent cards play for their full duration.

## Non-goals

- Transparent-alpha Manim rendering (we composite on black, not with alpha).
- Cross-session caching of Manim renders (orthogonal; existing hash-based cache stays).
- Rewriting narrate.py consolidation logic (stays as safety net).
- Re-architecting `score` or `stitch` beyond the title auto-invocation.

## Open questions for review

1. **Short-emotive ban threshold.** Proposed `word_count ≤ 8 AND exaggeration ≥ 0.30`. Confirm or adjust based on your test sweep.
2. **Storyboard as blocking gate vs opt-in.** Default: opt-in (user runs `storyboard_preview` explicitly). Alternative: `direct_prepare` refuses to run until storyboard has been generated and a `.storyboard_approved` marker exists. Lean opt-in; confirm.
3. **Manim overlay visual treatment.** Manim renders on solid black today. After overlay onto base, the black areas hide the base. Fine for this architecture. If we later want Manim transparency, revisit.
4. **Title card duration.** Auto-generated title uses tool's default duration. No attempt to match title length to opening narration or music. Acceptable?
