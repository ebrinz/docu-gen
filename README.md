<p align="center">
  <img src="assets/banner.svg" alt="docu-gen banner" width="100%"/>
</p>

# docu-gen

An [MCP server](https://modelcontextprotocol.io/) that transforms PDF technical specifications into narrated documentary videos — complete with animated scenes, chapter cards, ambient drone scoring, and word-level narration sync.

Give it a PDF spec, some images, and creative direction. It gives you back a polished MP4.

## How It Works

docu-gen exposes nine tools through the Model Context Protocol, designed to run in sequence:

| Step | Tool | What it does |
|------|------|-------------|
| 1 | **`init`** | Creates a new project directory with theme selection and config scaffold |
| 2 | **`plan`** | Extracts text from your PDF and generates a chapter structure with narration scripts |
| 3 | **`split`** | Breaks chapters into individual clips with emotion tagging, exaggeration levels, and pacing |
| 4 | **`narrate`** | Generates text-to-speech audio for each clip (OpenAI TTS or Chatterbox — see below) |
| 5 | **`align`** | Runs Whisper on each clip's audio to produce word-level timestamps for visual sync |
| 6a | **`direct_prepare`** | Gathers production plan visuals, clips, assets, and slide type registry; returns context for creative direction |
| 6b | **`direct_apply`** | Validates creative direction JSON, computes WAV-derived timing, writes back to clips.json |
| — | **`title`** | Optional standalone tool: generate a title card (particle, glitch, trace, or typewriter style) |
| 7 | **`render`** | Creates animated video scenes per clip using [Manim](https://www.manim.community/) and the project's theme |
| 8 | **`score`** | Generates a synthesized ambient drone score with per-chapter layers and transition sounds |
| 9 | **`stitch`** | Assembles clips, mixes narration with score (voice-activated ducking), outputs final MP4 |

Between each step you can review and edit the intermediate artifacts — especially `build/clips.json` after split, where you can tune emotion, pacing, and visual direction per clip before proceeding.

## Prerequisites

- **Python 3.10+**
- **ffmpeg** — for video/audio processing
- **An OpenAI API key** — used for plan generation (GPT-4o) and optionally narration (TTS)

## Voice Engines

docu-gen supports two TTS engines. **Chatterbox is recommended** for production — it runs fully local, supports voice cloning from a reference audio file, and gives you fine-grained control over expressiveness.

### Chatterbox (recommended — local)

[Chatterbox](https://github.com/resemble-ai/chatterbox) runs on-device via MLX (Apple Silicon) or PyTorch. No API key needed for narration. Clone any voice from a short reference clip.

```bash
pip install chatterbox-tts    # PyTorch
# or
pip install chatterbox-mlx    # Apple Silicon (MPS acceleration)
```

Configure in your project's `config.yaml`:

```yaml
voice:
  engine: chatterbox
  ref_audio: assets/my-voice.wav   # 5-30s reference clip for voice cloning
  exaggeration: 0.15               # Emotion intensity (0.0 = flat, 1.0 = max)
  cfg_weight: 0.8                  # Classifier-free guidance weight
  post_fx:                         # Optional audio post-processing
    ring_freq: 30                  # Ring modulator frequency (Hz)
    formant_shift: 1.05            # Formant shift multiplier
    dry_wet: 0.2                   # Effect mix (0.0 = dry, 1.0 = full effect)
```

> **Tip:** Keep exaggeration clamped relative to clip word count for natural delivery — short phrases (< 5 words) stay under 0.30, medium (< 15 words) under 0.50.

### OpenAI TTS (cloud)

Uses the OpenAI API. Simpler setup, but requires a network connection and API credits.

```bash
export OPENAI_API_KEY="sk-..."
```

```yaml
voice:
  engine: openai       # default if engine is omitted
  model: tts-1-hd
  voice: echo          # Options: alloy, echo, fable, nova, onyx, shimmer
```

## Whisper Alignment (local)

The `align` tool uses [OpenAI Whisper](https://github.com/openai/whisper) locally to transcribe each narration clip, then cross-correlates the transcription against the ground-truth text to produce word-level timestamps. These timestamps drive visual sync — animation cues, text reveals, and data transitions all key off `word_times` in `clips.json`.

```bash
pip install openai-whisper
```

Whisper runs entirely on-device (no API calls). The `small` model is used by default — accurate enough for timestamp alignment while keeping inference fast. On Apple Silicon, it will use MPS acceleration automatically.

### Setting up your API key

The `plan` tool calls the OpenAI API for chapter generation. If using OpenAI TTS for narration, the same key is used there too.

```bash
export OPENAI_API_KEY="sk-..."
```

Add this to your shell profile (`~/.zshrc`, `~/.bashrc`, etc.) so it persists across sessions.

## Quick Start

```bash
git clone https://github.com/ebrinz/docu-gen.git
cd docu-gen
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Local voice + alignment (recommended)
pip install chatterbox-mlx     # or chatterbox-tts for PyTorch
pip install openai-whisper

cp example.mcp.json .mcp.json
```

Then open a Claude Code session in the `docu-gen` directory and start prompting. The nine `docugen` tools will be available automatically.

## Connecting to Claude Code

An `example.mcp.json` is included in the repo. To activate the MCP server:

```bash
cp example.mcp.json .mcp.json
```

That's it. The next time you start a Claude Code session in this directory, the `docugen` tools will be available.

> **Note:** `.mcp.json` is gitignored so your local copy won't interfere with the repo.

### Other MCP Clients

For Claude Desktop, add to your config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "docugen": {
      "command": "/path/to/docu-gen/.venv/bin/python",
      "args": ["-m", "docugen.server"]
    }
  }
}
```

Any client that supports MCP stdio transport can connect using `.venv/bin/python -m docugen.server`.

## Usage

### 1. Create a project directory

Copy the included `example/` directory and add your own PDF spec and images:

```
my-project/
├── config.yaml    # Project settings (title, voice, video, drone config)
├── spec.pdf       # Your technical specification
├── prompt.txt     # Creative direction for the documentary tone
└── images/        # Visual assets (PNG, JPG, GIF, WEBP)
    ├── banner.png
    └── diagram.png
```

You can put project directories anywhere on your filesystem.

### 2. Run the pipeline

Once connected to your MCP client, use the tools in order. Each tool takes the path to your project directory:

```
→ init("my-project")
  Creates project scaffold

→ plan("/path/to/my-project")
  Review and edit build/plan.json

→ split("/path/to/my-project")
  Review and edit build/clips.json — tune emotion, pacing, visuals per clip

→ narrate("/path/to/my-project")
  Check build/narration/*.wav — skips existing files on re-runs

→ align("/path/to/my-project")
  Adds word_times to clips.json — word-level timestamps via Whisper

→ direct_prepare("/path/to/my-project")
  Returns context summary — review and decide creative direction per clip

→ direct_apply("/path/to/my-project", direction_json)
  Validates direction, computes timing — review clips.json before render

→ title("/path/to/my-project")
  Optional: generate standalone title card (particle, glitch, trace, typewriter)

→ render("/path/to/my-project")
  Preview build/clips/*.mp4 — Manim scenes per clip

→ score("/path/to/my-project")
  Check build/score.wav — ambient drone with chapter transitions

→ stitch("/path/to/my-project")
  Final output: build/final.mp4
```

All generated artifacts go into a `build/` subdirectory inside your project.

### Configuration

See `example/config.yaml` for a complete template. Key options:

```yaml
title: "My Documentary"
voice:
  engine: chatterbox               # "chatterbox" (recommended) or "openai"
  ref_audio: assets/my-voice.wav   # Required for chatterbox
  exaggeration: 0.15               # Chatterbox emotion intensity
  # --- or for OpenAI TTS ---
  # engine: openai
  # model: tts-1-hd
  # voice: echo
video:
  resolution: 1080p
  fps: 60
drone:
  cutoff_hz: 400       # Low-pass filter frequency
  duck_db: -18         # Voice ducking amount (dB)
  rt60: 1.5            # Reverb decay time (seconds)
  cue_freq: 220        # Chapter transition cue frequency (Hz)
```

### Creative Direction

The `prompt.txt` file guides the AI's documentary style. See `example/prompt.txt` for a starting point. Example:

```
Produce a documentary about this device in the style of a calm, authoritative
tech explainer. Open with a hook about the problem it solves. Keep chapters
focused — one concept per chapter. Use the banner image for intro and outro.
```

## Project Structure

```
src/docugen/
├── server.py              # MCP server — 9 tools exposed via stdio
├── config.py              # Configuration loading & defaults
├── split.py               # Chapter → clip splitting, emotion tagging, pacing
├── align.py               # Whisper transcription → word-level timestamp alignment
├── direct.py              # Creative direction: prepare context + apply validated direction JSON
├── drone.py               # Synthetic ambient drone audio generation
├── themes/
│   ├── base.py            # Base theme interface
│   └── biopunk.py         # Biopunk Imperial theme — scene rendering, transitions, FX
└── tools/
    ├── init_project.py    # Project scaffolding
    ├── plan.py            # PDF extraction & chapter planning (OpenAI)
    ├── narrate.py         # TTS generation (Chatterbox local or OpenAI cloud)
    ├── render.py          # Manim scene rendering per clip
    ├── score.py           # Per-chapter drone score with transition sounds
    ├── stitch.py          # Audio mixing & video concatenation
    └── title.py           # Standalone title card generator (particle, glitch, trace, typewriter)
```

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/
```

## Roadmap

Data visualization is being rebuilt. The current slide-type grammar (~11 primitives) renders generic Manim templates with labels but no real axes, units, or source data — so every data-bearing clip tends to look the same regardless of what the narration is saying. The rebuild introduces a typed grammar of ~22 primitives that render real charts from real data, a new `viz_extract` tool that decodes the source PDF's charts/tables into structured JSON, and an `llm_custom` escape hatch for clips that don't fit the grammar.

Full design: [`docs/superpowers/specs/2026-04-16-manim-data-viz-design.md`](docs/superpowers/specs/2026-04-16-manim-data-viz-design.md)

### Phase 1 — MVP grammar (in progress)

Ship the typed grammar end-to-end, validated against the parse-evols-yeast pitch.

- [ ] `themes/primitives/` package — auto-discovered registry, one file per primitive
- [ ] Upgrade existing primitives with real schemas: `bar_chart`, `counter`, `before_after`, `callout`
- [ ] New data viz primitives: `line_chart`, `tree`, `timeline`
- [ ] Escape hatch: `llm_custom` renderer with compile-retry (max 3) loop
- [ ] Migrate content primitives into the new layout (no behavior change): `title`, `chapter_card`, `ambient_field`, `svg_reveal`, `photo_organism`
- [ ] `viz_extract` MCP tool — PDF → `build/pdf_data.json` via Claude vision, sidecar-hashed for caching
- [ ] Extended `direct_prepare` — attaches `pdf_data.json` + primitive schemas to the direction context
- [ ] Extended `direct_apply` — schema validation per primitive, rejects malformed specs before render
- [ ] `themes/biopunk.py` refactor — 500-line method-map replaced by a thin dispatcher to primitives
- [ ] Deprecate `dot_merge` and `remove_reveal` (flagged in registry; still functional for back-compat)

**Acceptance:** parse-evols-yeast renders end-to-end, ≥60% of data-bearing clips use a typed primitive (not `llm_custom`), output visibly grounded in real data.

### Phase 2 — Expand grammar

Add the 9 remaining data viz primitives once MVP proves the pipeline.

- [ ] `stacked_area` — composition over time
- [ ] `scatter` — 2D distribution with optional size/color encoding
- [ ] `grouped_bar` — multi-series categorical comparison
- [ ] `pie_donut` — share (summed to 100%)
- [ ] `histogram` — distribution from raw or pre-binned values
- [ ] `sankey` — flow between categorical stages
- [ ] `funnel` — stepped conversion
- [ ] `network` — nodes + edges with force layout
- [ ] `quadrant` — 2×2 positioning matrix

### Phase 3 — Future

Unscoped, in rough priority order.

- [ ] Second theme (validates theme-owned-emphasis design, establishes theme-swap pattern)
- [ ] Matplotlib/Plotly fallback renderer — emit static frames for chart types Manim handles poorly (dense scatter, heatmaps)
- [ ] `llm_custom` promotion telemetry — flag recurring custom_script patterns as candidates for new typed primitives
- [ ] Perilux migration off the legacy `plan.json` pipeline onto `clips.json` + primitives
- [ ] `pdf_data.json` editing UI (currently hand-edit JSON; a simple web viewer would speed review)

## License

MIT
