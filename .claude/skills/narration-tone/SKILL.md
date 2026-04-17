---
name: narration-tone
description: Use when running or editing the docugen narrate stage (Chatterbox MLX), setting per-clip exaggeration, choosing a project wit level, or diagnosing robotic-voice distortion on short clips
---

# Narration Tone

## Overview

Three invariants for docugen narration, calibrated empirically against `robo.flac`:

1. **1-word clips need low emotion.** Anything else is free.
2. **Robo voice uses vocode post-fx.** Raw Chatterbox is not the project sound.
3. **Wit is a project dial**, set once in `prompt.txt`, applied consistently by `split`.

## When to Use

- About to call `mcp__docugen__narrate`
- Editing `clips.json` (`text`, `exaggeration`)
- Diagnosing off-sounding clips
- Setting voice defaults in `config.yaml`

Not for OpenAI TTS or raw-voice projects.

## Rule 1 — 1-Word Clips Need Low Emotion

Calibrated from `scripts/calibrate_chatterbox.py` (9 word-counts × 6 exaggerations):

| word_count | safe exaggeration |
|---|---|
| 1 | ≤ 0.25 |
| 2 | 0.30–0.60 (sweet spots ~0.35 and ~0.55) |
| ≥ 3 | any (0.15–0.70) |

**This voice favors high emotion** — don't globally clamp. Push exaggeration up on 3+ word clips; only 1-word clips need restraint.

**Audit before narrate:**

```python
from docugen.tools.narrate import _detect_short_hot_clips
import json
data = json.loads(open("projects/<name>/build/clips.json").read())
all_clips = [c for ch in data["chapters"] for c in ch["clips"]]
for i in _detect_short_hot_clips(all_clips):
    c = all_clips[i]
    print(c["clip_id"], len(c["text"].split()), c.get("exaggeration"), repr(c["text"]))
```

`_detect_short_hot_clips` uses `SHORT_WORD_LIMIT=1, HIGH_EXAGGERATION=0.3` — matches Rule 1 exactly.

**Fix options, in order of preference:**

1. **Merge narration** into preceding clip (`text=""`, `exaggeration=null`) — preserves visual rhythm, one WAV spans multiple clips. Requires pipeline support; not wired up yet.
2. **Rewrite to ≥ 2 words** if the beat can take it.
3. **Clamp exaggeration to 0.25** — safe, reversible, loses punch.

## Rule 2 — Vocode Post-FX

Robo voice default:

```yaml
voice:
  engine: chatterbox
  ref_audio: assets/robo.flac
  exaggeration: 0.15
  cfg_weight: 0.8
  post_fx:
    ring_freq: 30
    formant_shift: 1.05
    dry_wet: 0.2
```

Missing `post_fx` = raw Chatterbox = wrong project sound. Add it unless the project opts out.

## Rule 3 — Wit Dial

Set once per project in `prompt.txt`, applied by `split` when drafting narration:

| Dial | Feel | Example |
|---|---|---|
| dry | data-forward, minimal embellishment | "Two out of 2,000 compounds worked." |
| wry | observational irony | "Two out of 2,000. Not great odds." |
| punchy | short beats, rhythmic | "Two. Out of two thousand." |

Punchy creates more 1-word clips → more exposure to Rule 1. Compatible, but audit more carefully.

## Common Mistakes

| Mistake | Reality |
|---|---|
| "Detection is called from narrate" | It's not — audit manually before calling narrate |
| "Globally lower exaggeration to be safe" | Kills emotion on all clips. Only 1-word clips need it. |
| "Skip post-fx, it's dressing" | Vocode is the signature sound. Not optional. |
| "Pick wit per clip" | Dial drifts. Fix once in `prompt.txt`. |
| "Merge = delete the clip" | Narration-only merge: text=""; clip still drives visuals via neighbor's word_times. |

## Red Flags

- 1-word clip with exaggeration > 0.25 — fix before narrate
- `chatterbox` engine with no `post_fx` block — add it
- Per-clip exaggeration ≥ 0.5 on a 1-word line — guaranteed off
