<p align="center">
  <img src="assets/banner.svg" alt="docu-gen banner" width="100%"/>
</p>

# docu-gen

An [MCP server](https://modelcontextprotocol.io/) that transforms PDF technical specifications into narrated documentary videos — complete with animated scenes, chapter cards, and ambient drone audio.

Give it a PDF spec, some images, and creative direction. It gives you back a polished MP4.

## How It Works

docu-gen exposes four tools through the Model Context Protocol, designed to run in sequence:

| Step | Tool | What it does |
|------|------|-------------|
| 1 | **`plan`** | Extracts text from your PDF and generates a chapter structure with narration scripts |
| 2 | **`narrate`** | Generates text-to-speech audio for each chapter using OpenAI TTS |
| 3 | **`render`** | Creates animated video scenes using [Manim](https://www.manim.community/) — title cards, image galleries with Ken Burns motion, infographic diagrams |
| 4 | **`stitch`** | Combines everything into a final MP4 with synthesized ambient drone audio and voice-activated ducking |

Between each step you can review and edit the intermediate artifacts (especially `plan.json`) before proceeding.

## Prerequisites

- **Python 3.10+**
- **ffmpeg** — for video/audio processing
- **An OpenAI API key** — used for plan generation (GPT-4o) and narration (TTS)

### Setting up your API key

The `plan` and `narrate` tools call the OpenAI API. You need to set your key as an environment variable:

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
cp example.mcp.json .mcp.json
```

Then open a Claude Code session in the `docu-gen` directory and start prompting. The four `docugen` tools (`plan`, `narrate`, `render`, `stitch`) will be available automatically.

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
→ plan("/path/to/my-project")
  Review and edit build/plan.json

→ narrate("/path/to/my-project")
  Check build/narration/*.wav

→ render("/path/to/my-project")
  Preview build/clips/*.mp4

→ stitch("/path/to/my-project")
  Final output: build/final.mp4
```

All generated artifacts go into a `build/` subdirectory inside your project.

### Configuration

See `example/config.yaml` for a complete template. Key options:

```yaml
title: "My Documentary"
voice:
  model: tts-1-hd
  voice: echo          # Options: alloy, echo, fable, nova, onyx, shimmer
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
├── server.py          # MCP server & tool definitions
├── config.py          # Configuration loading & defaults
├── drone.py           # Synthetic ambient drone audio generation
└── tools/
    ├── plan.py        # PDF extraction & chapter planning (OpenAI)
    ├── narrate.py     # Text-to-speech generation (OpenAI)
    ├── render.py      # Manim scene rendering
    └── stitch.py      # Audio mixing & video concatenation
```

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/
```

## License

MIT
