# Docugen MCP Server — Design Spec

## Overview

A reusable MCP server that turns a LaTeX PDF spec + images + creative prompt into a chaptered documentary video with AI narration and animated visuals. Pipeline methodology lifted from the [heiroglyphy](../../../heiroglyphy) project and generalized.

## Input

- **spec.pdf** — LaTeX PDF containing the strategy/content to document
- **images/** — folder of PNGs/JPGs (screenshots, photos, architecture diagrams)
- **prompt.txt** — creative direction for how the AI should structure and narrate the documentary
- **config.yaml** — project-level settings (voice, resolution, drone params)

## Output

- **final.mp4** — chaptered documentary video (intro, ch1..N, outro) with TTS narration, Manim visuals, composited images, and background drone audio

## Architecture

### MCP Server with 4 Stage Tools

The server exposes four tools, each corresponding to a pipeline stage. The user invokes them sequentially through any MCP client (Claude Code, etc.), reviewing and editing artifacts between stages.

```
plan → narrate → render → stitch
```

Each tool takes a project path and reads/writes to `build/` within that project directory.

## Project Structure

```
docu-mentation/
├── src/
│   └── docugen/
│       ├── __init__.py
│       ├── server.py           # MCP server (FastMCP)
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── plan.py         # Tool: extract PDF → chapter plan JSON
│       │   ├── narrate.py      # Tool: chapter plan → TTS wav files
│       │   ├── render.py       # Tool: chapter plan + images → Manim mp4s
│       │   └── stitch.py       # Tool: combine clips + narration + drone → final mp4
│       ├── drone.py            # DSP drone synthesis (from heiroglyphy)
│       └── config.py           # Project config loader
├── projects/
│   └── example/
│       ├── config.yaml
│       ├── spec.pdf
│       ├── prompt.txt
│       ├── images/
│       └── build/              # Generated artifacts (gitignored)
│           ├── plan.json
│           ├── narration/      # Per-chapter TTS wavs
│           ├── clips/          # Per-chapter Manim mp4s
│           ├── drone.wav
│           └── final.mp4
├── pyproject.toml
└── README.md
```

## MCP Tools

### 1. `plan`

**Input:** `project_path` (string) — path to a project directory

**Process:**
1. Extract text from `spec.pdf` using PyMuPDF (fitz)
2. Read `prompt.txt` for creative direction
3. List available images in `images/`
4. Send extracted text + prompt + image list to OpenAI ChatGPT
5. ChatGPT returns a structured chapter plan
6. Write `build/plan.json`

**Output:** Status message + path to `plan.json`. User reviews/edits before proceeding.

### 2. `narrate`

**Input:** `project_path` (string)

**Process:**
1. Read `build/plan.json` and `config.yaml`
2. For each chapter, call OpenAI TTS API (`tts-1-hd`, voice: `echo`)
3. Cache WAV files in `build/narration/` (e.g., `intro.wav`, `ch1.wav`)
4. Retry with exponential backoff (3 attempts)
5. If generated audio exceeds duration estimate, re-generate at higher speed (1.1x → 1.25x)

**Output:** Status message + list of generated WAV files with durations.

### 3. `render`

**Input:** `project_path` (string)

**Process:**
1. Read `build/plan.json` and `config.yaml`
2. Read narration durations from `build/narration/` to sync scene lengths
3. For each chapter, generate a Manim scene:
   - **`manim` scene_type** (intro/outro/chapter cards): animated title text, project title, chapter numbers
   - **`mixed` scene_type**: Manim title card + composited images with Ken Burns motion + text overlays
4. Render each scene at 1080p60 to `build/clips/`

**Output:** Status message + list of rendered clip paths.

### 4. `stitch`

**Input:** `project_path` (string)

**Process:**
1. Synthesize drone audio track:
   - Pink noise base (Voss-McCartney algorithm)
   - Reactive sine cues at chapter transitions (220Hz, attack=0.1s, decay=2s)
   - Convolution reverb (synthetic IR, RT60=1.5s)
   - Butterworth low-pass filter at configurable cutoff (default 400Hz)
2. Mix narration + drone:
   - Voice-activated ducking (drone attenuated by configurable dB, default -18dB, when narration present)
   - Peak normalization to -1dB
3. Concatenate video clips in chapter order via FFmpeg
4. Merge mixed audio onto concatenated video
5. Write `build/final.mp4`

**Output:** Status message + path to final video + total duration.

## Plan JSON Schema

```json
{
  "title": "Documentary Title",
  "chapters": [
    {
      "id": "intro",
      "title": "Introduction",
      "narration": "Full narration script text for this chapter.",
      "scene_type": "manim",
      "images": [],
      "duration_estimate": 15.0
    },
    {
      "id": "ch1",
      "title": "Chapter Title",
      "narration": "Narration script...",
      "scene_type": "mixed",
      "images": ["screenshot1.png", "arch_diagram.png"],
      "duration_estimate": 45.0
    },
    {
      "id": "outro",
      "title": "Conclusion",
      "narration": "Closing narration...",
      "scene_type": "manim",
      "images": [],
      "duration_estimate": 12.0
    }
  ]
}
```

## Config Format

```yaml
# config.yaml
title: "My Documentary"
voice:
  model: tts-1-hd
  voice: echo
video:
  resolution: 1080p
  fps: 60
drone:
  cutoff_hz: 400
  duck_db: -18
  rt60: 1.5
  cue_freq: 220
```

## Manim Scene Design

### Intro Scene
- Dark background (#0f0f1a)
- Project title fades in (gold #f5c518, large)
- Subtitle/tagline fades in below (teal #3ec9a7)
- Duration synced to intro narration

### Chapter Card Scene
- Chapter number + title animates in
- Brief pause, then transition out

### Mixed Content Scene
- Chapter card intro (2-3s)
- Images composited with Ken Burns (slow zoom/pan)
- Text overlays for key points if specified in plan
- Duration matched to narration length

### Outro Scene
- Summary title card
- Credits/attribution
- Fade to black

## Drone Synthesis (from heiroglyphy)

Lifted from `heiroglyphy/docs/audio/generate_drone.py`:

- **Pink noise:** Voss-McCartney vectorized 16-row implementation
- **Reactive cues:** Sine waves at chapter transitions (configurable frequency, attack/decay envelope)
- **Convolution reverb:** Synthetic impulse response with configurable RT60
- **Low-pass filter:** Butterworth IIR at configurable cutoff
- **Voice-activated ducking:** RMS detection on narration track, smooth envelope, configurable attenuation

## Dependencies

### Python Packages
- `mcp` / `fastmcp` — MCP server framework
- `manim` — video rendering
- `manimpango` — font rendering in Manim
- `openai` — TTS API + ChatGPT for planning
- `pymupdf` — PDF text extraction
- `numpy` — DSP operations
- `scipy` — signal processing (filters, convolution)
- `pyyaml` — config parsing

### System Dependencies
- `ffmpeg` / `ffprobe` — audio/video merge and concatenation
- Python 3.10+

### Environment Variables
- `OPENAI_API_KEY` — required for TTS and planning stages

## Workflow Example

```
User: "plan projects/retouchery"
→ Extracts PDF, generates chapter plan, writes plan.json
→ User reviews plan.json, edits narration scripts if needed

User: "narrate projects/retouchery"
→ Generates TTS for each chapter, writes WAVs
→ User listens to clips, re-runs if needed

User: "render projects/retouchery"
→ Renders Manim scenes per chapter, writes MP4 clips
→ User previews clips

User: "stitch projects/retouchery"
→ Synthesizes drone, mixes audio, concatenates video, writes final.mp4
```
