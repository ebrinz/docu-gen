# Docugen MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an MCP server that turns a LaTeX PDF + images + prompt into a chaptered documentary video with AI narration, Manim visuals, and drone audio.

**Architecture:** Four stage-based MCP tools (plan, narrate, render, stitch) backed by a shared config loader. Each tool reads/writes artifacts in a project's `build/` directory. DSP drone synthesis and audio mixing adapted from heiroglyphy.

**Tech Stack:** FastMCP, OpenAI (TTS + chat), Manim, PyMuPDF, NumPy, SciPy, FFmpeg

---

## File Structure

```
docu-mentation/
├── src/
│   └── docugen/
│       ├── __init__.py              # Package init
│       ├── server.py                # FastMCP server, tool registration
│       ├── config.py                # Load/validate config.yaml
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── plan.py              # PDF extract → chapter plan JSON
│       │   ├── narrate.py           # Chapter plan → TTS wav files
│       │   ├── render.py            # Chapter plan + images → Manim mp4s
│       │   └── stitch.py            # Combine clips + narration + drone → final mp4
│       └── drone.py                 # DSP drone synthesis
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_plan.py
│   ├── test_drone.py
│   ├── test_narrate.py
│   ├── test_render.py
│   └── test_stitch.py
├── projects/
│   └── example/
│       ├── config.yaml
│       ├── prompt.txt
│       └── images/
├── pyproject.toml
└── .gitignore
```

---

### Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `src/docugen/__init__.py`
- Create: `.gitignore`
- Create: `projects/example/config.yaml`
- Create: `projects/example/prompt.txt`
- Create: `projects/example/images/.gitkeep`
- Create: `tests/__init__.py`

- [ ] **Step 1: Initialize git repo**

```bash
cd /Users/crashy/Development/docu-mentation
git init
```

- [ ] **Step 2: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "docugen"
version = "0.1.0"
description = "MCP server: PDF spec → chaptered documentary video"
requires-python = ">=3.10"
dependencies = [
    "mcp[cli]>=1.0.0",
    "openai>=1.0.0",
    "manim>=0.18.0",
    "manimpango>=0.5.0",
    "pymupdf>=1.24.0",
    "numpy>=1.24.0",
    "scipy>=1.10.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = ["pytest>=7.0"]

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 3: Create src/docugen/__init__.py**

```python
"""Docugen: PDF spec → chaptered documentary video via MCP."""
```

- [ ] **Step 4: Create .gitignore**

```gitignore
__pycache__/
*.pyc
*.egg-info/
dist/
build/
.venv/
projects/*/build/
media/
*.wav
*.mp4
```

- [ ] **Step 5: Create example project skeleton**

`projects/example/config.yaml`:
```yaml
title: "Example Documentary"
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

`projects/example/prompt.txt`:
```
Create a clear, engaging documentary that explains the key concepts in this spec.
Use a calm, authoritative tone. Break into logical chapters.
Each chapter should focus on one main idea.
```

`projects/example/images/.gitkeep`: empty file

- [ ] **Step 6: Create tests/__init__.py**

Empty file.

- [ ] **Step 7: Install in dev mode and verify**

```bash
cd /Users/crashy/Development/docu-mentation
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Expected: installs without errors.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml src/ tests/ projects/ .gitignore
git commit -m "feat: project scaffold with pyproject.toml and example project"
```

---

### Task 2: Config Loader

**Files:**
- Create: `src/docugen/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
import pytest
from pathlib import Path
from docugen.config import load_config

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def example_config(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "title: Test Doc\n"
        "voice:\n"
        "  model: tts-1-hd\n"
        "  voice: echo\n"
        "video:\n"
        "  resolution: 1080p\n"
        "  fps: 60\n"
        "drone:\n"
        "  cutoff_hz: 400\n"
        "  duck_db: -18\n"
        "  rt60: 1.5\n"
        "  cue_freq: 220\n"
    )
    return tmp_path


def test_load_config_reads_yaml(example_config):
    cfg = load_config(example_config)
    assert cfg["title"] == "Test Doc"
    assert cfg["voice"]["model"] == "tts-1-hd"
    assert cfg["voice"]["voice"] == "echo"
    assert cfg["video"]["fps"] == 60
    assert cfg["drone"]["cutoff_hz"] == 400


def test_load_config_defaults(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("title: Minimal\n")
    cfg = load_config(tmp_path)
    assert cfg["voice"]["model"] == "tts-1-hd"
    assert cfg["voice"]["voice"] == "echo"
    assert cfg["video"]["resolution"] == "1080p"
    assert cfg["video"]["fps"] == 60
    assert cfg["drone"]["cutoff_hz"] == 400
    assert cfg["drone"]["duck_db"] == -18
    assert cfg["drone"]["rt60"] == 1.5
    assert cfg["drone"]["cue_freq"] == 220


def test_load_config_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/crashy/Development/docu-mentation
source .venv/bin/activate
pytest tests/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'docugen.config'`

- [ ] **Step 3: Write minimal implementation**

`src/docugen/config.py`:
```python
"""Load and validate project config.yaml with defaults."""

from pathlib import Path
import yaml

DEFAULTS = {
    "voice": {
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


def _deep_merge(defaults: dict, overrides: dict) -> dict:
    """Merge overrides into defaults, recursing into nested dicts."""
    result = dict(defaults)
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(project_path: str | Path) -> dict:
    """Load config.yaml from a project directory, applying defaults."""
    project_path = Path(project_path)
    config_file = project_path / "config.yaml"
    if not config_file.exists():
        raise FileNotFoundError(f"No config.yaml in {project_path}")

    with open(config_file) as f:
        raw = yaml.safe_load(f) or {}

    return _deep_merge(DEFAULTS, raw)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_config.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/docugen/config.py tests/test_config.py
git commit -m "feat: config loader with defaults and deep merge"
```

---

### Task 3: Plan Tool — PDF Extraction + Chapter Planning

**Files:**
- Create: `src/docugen/tools/__init__.py`
- Create: `src/docugen/tools/plan.py`
- Create: `tests/test_plan.py`

- [ ] **Step 1: Write the failing test for PDF extraction**

`tests/test_plan.py`:
```python
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from docugen.tools.plan import extract_pdf_text, generate_plan, list_images


@pytest.fixture
def project_dir(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "title: Test Doc\n"
    )
    (tmp_path / "prompt.txt").write_text("Make it engaging.\n")
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "shot1.png").write_bytes(b"fake png")
    (tmp_path / "images" / "diagram.jpg").write_bytes(b"fake jpg")
    (tmp_path / "build").mkdir()
    return tmp_path


def test_list_images(project_dir):
    images = list_images(project_dir)
    assert sorted(images) == ["diagram.jpg", "shot1.png"]


def test_extract_pdf_text_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        extract_pdf_text(tmp_path / "nonexistent.pdf")


def test_generate_plan_writes_json(project_dir):
    fake_chapters = {
        "title": "Test Doc",
        "chapters": [
            {
                "id": "intro",
                "title": "Introduction",
                "narration": "Welcome to this documentary.",
                "scene_type": "manim",
                "images": [],
                "duration_estimate": 10.0,
            }
        ],
    }

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps(fake_chapters)
    mock_client.chat.completions.create.return_value = mock_response

    with patch("docugen.tools.plan.OpenAI", return_value=mock_client):
        result = generate_plan(project_dir, pdf_text="Some spec content.")

    plan_path = project_dir / "build" / "plan.json"
    assert plan_path.exists()

    plan = json.loads(plan_path.read_text())
    assert plan["title"] == "Test Doc"
    assert len(plan["chapters"]) == 1
    assert plan["chapters"][0]["id"] == "intro"
    assert result == str(plan_path)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_plan.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

`src/docugen/tools/__init__.py`: empty file.

`src/docugen/tools/plan.py`:
```python
"""Plan tool: extract PDF text and generate chapter plan via OpenAI."""

import json
from pathlib import Path

import fitz  # PyMuPDF
from openai import OpenAI

from docugen.config import load_config

PLAN_SYSTEM_PROMPT = """\
You are a documentary planner. Given a technical spec and creative direction,
break the content into documentary chapters.

Return ONLY valid JSON matching this schema:
{
  "title": "Documentary Title",
  "chapters": [
    {
      "id": "intro" | "ch1" | "ch2" | ... | "outro",
      "title": "Chapter Title",
      "narration": "Full narration script for voiceover.",
      "scene_type": "manim" | "mixed",
      "images": ["filename.png"],
      "duration_estimate": 30.0
    }
  ]
}

Rules:
- Always start with an "intro" chapter (scene_type: "manim", no images)
- Always end with an "outro" chapter (scene_type: "manim", no images)
- Content chapters use scene_type "mixed" and reference available images
- Narration should be conversational, ~130 words per minute pace
- duration_estimate in seconds, based on narration length
- Assign images to the chapters where they're most relevant
"""


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract all text from a PDF file using PyMuPDF."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    doc = fitz.open(str(pdf_path))
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


def list_images(project_path: Path) -> list[str]:
    """List image filenames in the project's images/ directory."""
    project_path = Path(project_path)
    images_dir = project_path / "images"
    if not images_dir.exists():
        return []
    extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    return sorted(
        f.name for f in images_dir.iterdir()
        if f.suffix.lower() in extensions
    )


def generate_plan(project_path: str | Path, pdf_text: str | None = None) -> str:
    """Generate a chapter plan from a PDF spec + prompt via OpenAI.

    Args:
        project_path: Path to the project directory.
        pdf_text: Pre-extracted PDF text. If None, extracts from spec.pdf.

    Returns:
        Path to the written plan.json file.
    """
    project_path = Path(project_path)
    config = load_config(project_path)

    # Extract PDF text if not provided
    if pdf_text is None:
        pdf_path = project_path / "spec.pdf"
        pdf_text = extract_pdf_text(pdf_path)

    # Read creative prompt
    prompt_file = project_path / "prompt.txt"
    creative_prompt = prompt_file.read_text() if prompt_file.exists() else ""

    # List available images
    images = list_images(project_path)

    # Build user message
    user_message = (
        f"# Creative Direction\n{creative_prompt}\n\n"
        f"# Available Images\n{json.dumps(images)}\n\n"
        f"# Spec Content\n{pdf_text}"
    )

    # Call OpenAI
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": PLAN_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
        response_format={"type": "json_object"},
    )

    plan_text = response.choices[0].message.content
    plan = json.loads(plan_text)

    # Ensure title from config
    if "title" not in plan or not plan["title"]:
        plan["title"] = config.get("title", "Untitled Documentary")

    # Write plan.json
    build_dir = project_path / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    plan_path = build_dir / "plan.json"
    plan_path.write_text(json.dumps(plan, indent=2))

    return str(plan_path)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_plan.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/docugen/tools/ tests/test_plan.py
git commit -m "feat: plan tool — PDF extraction and chapter planning via OpenAI"
```

---

### Task 4: Narrate Tool — TTS Generation

**Files:**
- Create: `src/docugen/tools/narrate.py`
- Create: `tests/test_narrate.py`

- [ ] **Step 1: Write the failing test**

`tests/test_narrate.py`:
```python
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from docugen.tools.narrate import generate_narration


@pytest.fixture
def project_dir(tmp_path):
    (tmp_path / "config.yaml").write_text("title: Test\n")
    build = tmp_path / "build"
    build.mkdir()
    (build / "narration").mkdir()

    plan = {
        "title": "Test",
        "chapters": [
            {
                "id": "intro",
                "title": "Introduction",
                "narration": "Welcome to this test documentary.",
                "scene_type": "manim",
                "images": [],
                "duration_estimate": 10.0,
            },
            {
                "id": "ch1",
                "title": "Chapter One",
                "narration": "This is the first chapter about testing.",
                "scene_type": "mixed",
                "images": ["shot1.png"],
                "duration_estimate": 20.0,
            },
        ],
    }
    (build / "plan.json").write_text(json.dumps(plan))
    return tmp_path


def test_generate_narration_creates_wavs(project_dir):
    # Create a fake WAV response (44-byte header + silence)
    import struct
    sr = 24000
    n_samples = sr * 2  # 2 seconds
    data_size = n_samples * 2  # 16-bit
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + data_size, b'WAVE',
        b'fmt ', 16, 1, 1, sr, sr * 2, 2, 16,
        b'data', data_size,
    )
    fake_wav = header + b'\x00' * data_size

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = fake_wav
    mock_response.write_to_file = lambda path: Path(path).write_bytes(fake_wav)
    mock_client.audio.speech.create.return_value = mock_response

    with patch("docugen.tools.narrate.OpenAI", return_value=mock_client):
        result = generate_narration(project_dir)

    narration_dir = project_dir / "build" / "narration"
    assert (narration_dir / "intro.wav").exists()
    assert (narration_dir / "ch1.wav").exists()
    assert "intro.wav" in result
    assert "ch1.wav" in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_narrate.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

`src/docugen/tools/narrate.py`:
```python
"""Narrate tool: generate TTS audio for each chapter via OpenAI."""

import json
import time
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly
from math import gcd
from openai import OpenAI

from docugen.config import load_config

TARGET_SR = 44100


def _read_wav_duration(path: Path) -> float:
    """Get duration of a WAV file in seconds."""
    sr, data = wavfile.read(str(path))
    if data.ndim > 1:
        data = data[:, 0]
    return len(data) / sr


def _generate_single(client, chapter_id: str, text: str, model: str,
                     voice: str, output_path: Path, speed: float = 1.0) -> Path:
    """Call OpenAI TTS for a single chapter. Retries with exponential backoff."""
    if output_path.exists():
        return output_path

    for attempt in range(3):
        try:
            response = client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                response_format="wav",
                speed=speed,
            )
            response.write_to_file(str(output_path))
            return output_path
        except Exception as e:
            if attempt < 2:
                wait = 2 ** (attempt + 1)
                time.sleep(wait)
            else:
                raise


def generate_narration(project_path: str | Path) -> str:
    """Generate TTS narration WAVs for each chapter in plan.json.

    Returns a summary string listing generated files and durations.
    """
    project_path = Path(project_path)
    config = load_config(project_path)
    voice_config = config["voice"]

    plan_path = project_path / "build" / "plan.json"
    if not plan_path.exists():
        raise FileNotFoundError(f"No plan.json found. Run 'plan' first.")

    plan = json.loads(plan_path.read_text())
    narration_dir = project_path / "build" / "narration"
    narration_dir.mkdir(parents=True, exist_ok=True)

    client = OpenAI()
    results = []

    for chapter in plan["chapters"]:
        cid = chapter["id"]
        text = chapter["narration"]
        out_path = narration_dir / f"{cid}.wav"

        _generate_single(
            client, cid, text,
            model=voice_config["model"],
            voice=voice_config["voice"],
            output_path=out_path,
        )

        # Check duration vs estimate, speed up if needed
        duration = _read_wav_duration(out_path)
        estimate = chapter.get("duration_estimate", 999)

        if duration > estimate:
            for speed in [1.1, 1.15, 1.2, 1.25]:
                out_path.unlink(missing_ok=True)
                _generate_single(
                    client, cid, text,
                    model=voice_config["model"],
                    voice=voice_config["voice"],
                    output_path=out_path,
                    speed=speed,
                )
                duration = _read_wav_duration(out_path)
                if duration <= estimate:
                    break

        results.append(f"{cid}.wav ({duration:.1f}s)")

    return "Generated narration:\n" + "\n".join(results)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_narrate.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/docugen/tools/narrate.py tests/test_narrate.py
git commit -m "feat: narrate tool — TTS generation per chapter with speed adjustment"
```

---

### Task 5: Drone Synthesis

**Files:**
- Create: `src/docugen/drone.py`
- Create: `tests/test_drone.py`

- [ ] **Step 1: Write the failing test**

`tests/test_drone.py`:
```python
import numpy as np
import pytest
from docugen.drone import (
    pink_noise, sine_wave, apply_envelope, synthetic_reverb_ir,
    generate_drone_track,
)


def test_pink_noise_shape():
    rng = np.random.default_rng(42)
    noise = pink_noise(44100, rng)
    assert noise.shape == (44100,)
    assert np.max(np.abs(noise)) <= 1.0 + 1e-6


def test_sine_wave_frequency():
    sr = 44100
    signal = sine_wave(440.0, 1.0, sr=sr)
    assert len(signal) == sr
    # Check zero crossings approximate 440 Hz
    crossings = np.where(np.diff(np.sign(signal)))[0]
    # ~880 zero crossings per second for 440 Hz
    assert 850 < len(crossings) < 910


def test_apply_envelope_shape():
    signal = np.ones(44100)
    enveloped = apply_envelope(signal, attack_s=0.1, decay_s=0.5)
    assert enveloped.shape == signal.shape
    assert enveloped[0] == pytest.approx(0.0, abs=0.01)


def test_synthetic_reverb_ir_decays():
    ir = synthetic_reverb_ir(rt60=1.0)
    # Energy should decay: first quarter louder than last quarter
    quarter = len(ir) // 4
    first_energy = np.mean(ir[:quarter] ** 2)
    last_energy = np.mean(ir[-quarter:] ** 2)
    assert first_energy > last_energy * 10


def test_generate_drone_track_output():
    chapter_times = [0.0, 5.0, 10.0]
    total_duration = 15.0
    track = generate_drone_track(
        total_duration=total_duration,
        chapter_start_times=chapter_times,
        cutoff_hz=400,
        cue_freq=220,
        rt60=1.5,
        sr=44100,
    )
    expected_samples = int(total_duration * 44100)
    # Stereo output
    assert track.ndim == 2
    assert track.shape[1] == 2
    # Length within 1 second of expected
    assert abs(track.shape[0] - expected_samples) < 44100
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_drone.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

`src/docugen/drone.py`:
```python
"""Drone audio synthesis — adapted from heiroglyphy/docs/audio/generate_drone.py.

Generates a stereo ambient drone with reactive cues at chapter transitions.
"""

import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve

SR = 44100


def db_to_amp(db: float) -> float:
    return 10.0 ** (db / 20.0)


def pink_noise(n_samples: int, rng: np.random.Generator) -> np.ndarray:
    """Generate pink noise using vectorized Voss-McCartney algorithm."""
    n_rows = 16
    array = rng.standard_normal((n_rows, n_samples))
    for i in range(1, n_rows):
        step = 2 ** i
        n_unique = (n_samples + step - 1) // step
        values = rng.standard_normal(n_unique)
        array[i, :] = np.repeat(values, step)[:n_samples]
    result = array.sum(axis=0)
    result /= np.max(np.abs(result)) + 1e-10
    return result


def sine_wave(freq: float, duration: float, sr: int = SR, phase: float = 0.0) -> np.ndarray:
    t = np.arange(int(duration * sr)) / sr
    return np.sin(2 * np.pi * freq * t + phase)


def apply_envelope(signal: np.ndarray, attack_s: float, decay_s: float,
                   sustain_s: float = 0.0, sr: int = SR) -> np.ndarray:
    n = len(signal)
    envelope = np.ones(n)
    attack_n = int(attack_s * sr)
    decay_n = int(decay_s * sr)
    sustain_n = int(sustain_s * sr)

    if attack_n > 0:
        envelope[:attack_n] = np.linspace(0, 1, attack_n) ** 2
    decay_start = attack_n + sustain_n
    if decay_start < n and decay_n > 0:
        decay_end = min(decay_start + decay_n, n)
        actual_decay = decay_end - decay_start
        envelope[decay_start:decay_end] = np.linspace(1, 0, actual_decay) ** 2
        envelope[decay_end:] = 0.0

    return signal * envelope


def synthetic_reverb_ir(rt60: float = 1.5, sr: int = SR,
                        rng: np.random.Generator | None = None) -> np.ndarray:
    if rng is None:
        rng = np.random.default_rng(0)
    n_samples = int(rt60 * 2 * sr)
    noise = rng.standard_normal(n_samples)
    decay = np.exp(-3.0 * np.arange(n_samples) / (rt60 * sr))
    return noise * decay


def _bandpass(signal: np.ndarray, low: float, high: float,
              sr: int = SR, order: int = 4) -> np.ndarray:
    sos = butter(order, [low, high], btype="band", fs=sr, output="sos")
    return sosfilt(sos, signal)


def _lowpass(signal: np.ndarray, cutoff: float,
             sr: int = SR, order: int = 4) -> np.ndarray:
    sos = butter(order, cutoff, btype="low", fs=sr, output="sos")
    return sosfilt(sos, signal)


def _generate_base(total_samples: int, rng: np.random.Generator,
                   sr: int = SR) -> np.ndarray:
    """Base drone: fundamental + harmonics + pink noise. Returns stereo (N, 2)."""
    fundamental = 65.0
    duration = total_samples / sr

    drone = np.tanh(1.5 * sine_wave(fundamental, duration, sr))
    drone += db_to_amp(-6) * sine_wave(fundamental * 2, duration, sr)
    drone += db_to_amp(-12) * sine_wave(fundamental * 3, duration, sr)
    drone += db_to_amp(-18) * sine_wave(fundamental * 5, duration, sr)

    lfo = 1.0 + 0.15 * sine_wave(0.08, duration, sr)
    drone *= lfo

    noise = pink_noise(total_samples, rng)
    noise = _bandpass(noise, 100, 800, sr)
    noise *= db_to_amp(-24)
    drone += noise
    drone /= np.max(np.abs(drone)) + 1e-10

    # Stereo with slight detuning
    left = drone
    right = np.tanh(1.5 * sine_wave(fundamental + 0.5, duration, sr))
    right += db_to_amp(-6) * sine_wave(fundamental * 2 + 0.5, duration, sr)
    right += db_to_amp(-12) * sine_wave(fundamental * 3 + 0.5, duration, sr)
    right += db_to_amp(-18) * sine_wave(fundamental * 5 + 0.5, duration, sr)
    right *= lfo
    right += noise
    right /= np.max(np.abs(right)) + 1e-10

    return np.column_stack([left, right])


def _generate_cue(freq: float, duration: float, attack: float,
                  decay: float, sr: int = SR) -> np.ndarray:
    """Generate a reactive sine cue. Returns stereo (N, 2)."""
    signal = sine_wave(freq, duration, sr)
    signal = apply_envelope(signal, attack_s=attack, decay_s=decay)
    signal *= db_to_amp(-12)
    return np.column_stack([signal, signal])


def _overlay(base: np.ndarray, layer: np.ndarray, start_sample: int) -> np.ndarray:
    """Overlay a stereo layer onto base at a given sample position."""
    if layer.ndim == 1:
        layer = np.column_stack([layer, layer])
    end = start_sample + layer.shape[0]
    if end > base.shape[0]:
        layer = layer[:base.shape[0] - start_sample]
        end = base.shape[0]
    if start_sample < base.shape[0]:
        base[start_sample:end] += layer
    return base


def generate_drone_track(
    total_duration: float,
    chapter_start_times: list[float],
    cutoff_hz: float = 400,
    cue_freq: float = 220,
    rt60: float = 1.5,
    sr: int = SR,
) -> np.ndarray:
    """Generate a complete drone track with chapter transition cues.

    Args:
        total_duration: Total duration in seconds.
        chapter_start_times: List of chapter start times in seconds for reactive cues.
        cutoff_hz: Low-pass filter cutoff.
        cue_freq: Frequency of transition cues.
        rt60: Reverb decay time.
        sr: Sample rate.

    Returns:
        Stereo numpy array (N, 2) of float64 samples, normalized.
    """
    total_samples = int(total_duration * sr)
    rng = np.random.default_rng(42)

    # Base drone
    drone = _generate_base(total_samples, rng, sr)

    # Reactive cues at chapter transitions
    for t in chapter_start_times:
        cue = _generate_cue(cue_freq, 4.0, attack=0.1, decay=2.0, sr=sr)
        start_sample = int(t * sr)
        drone = _overlay(drone, cue, start_sample)

    # Apply low-pass filter
    drone[:, 0] = _lowpass(drone[:, 0], cutoff_hz, sr)
    drone[:, 1] = _lowpass(drone[:, 1], cutoff_hz, sr)

    # Apply reverb
    ir = synthetic_reverb_ir(rt60=rt60, sr=sr, rng=rng)
    for ch in range(2):
        wet = fftconvolve(drone[:, ch], ir, mode="full")[:total_samples]
        drone[:, ch] = 0.7 * drone[:, ch] + 0.3 * wet

    # Fade in (3s) and fade out (5s)
    fade_in = int(3.0 * sr)
    fade_out = int(5.0 * sr)
    drone[:fade_in, 0] *= np.linspace(0, 1, fade_in)
    drone[:fade_in, 1] *= np.linspace(0, 1, fade_in)
    drone[-fade_out:, 0] *= np.linspace(1, 0, fade_out)
    drone[-fade_out:, 1] *= np.linspace(1, 0, fade_out)

    # Normalize
    peak = np.max(np.abs(drone)) + 1e-10
    drone = drone / peak * 0.9

    return drone
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_drone.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/docugen/drone.py tests/test_drone.py
git commit -m "feat: drone synthesis — pink noise, reactive cues, reverb, filtering"
```

---

### Task 6: Render Tool — Manim Scene Generation

**Files:**
- Create: `src/docugen/tools/render.py`
- Create: `tests/test_render.py`

- [ ] **Step 1: Write the failing test**

`tests/test_render.py`:
```python
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from docugen.tools.render import build_manim_script, render_chapter


def test_build_manim_script_intro():
    chapter = {
        "id": "intro",
        "title": "Introduction",
        "narration": "Welcome to this documentary.",
        "scene_type": "manim",
        "images": [],
        "duration_estimate": 10.0,
    }
    script = build_manim_script(
        chapter=chapter,
        doc_title="Test Documentary",
        duration=10.0,
        images_dir=Path("/fake/images"),
    )
    assert "class Scene_intro" in script
    assert "Test Documentary" in script
    assert "Introduction" in script


def test_build_manim_script_mixed_with_images():
    chapter = {
        "id": "ch1",
        "title": "Chapter One",
        "narration": "This chapter has images.",
        "scene_type": "mixed",
        "images": ["shot1.png", "diagram.jpg"],
        "duration_estimate": 30.0,
    }
    script = build_manim_script(
        chapter=chapter,
        doc_title="Test Documentary",
        duration=30.0,
        images_dir=Path("/fake/images"),
    )
    assert "class Scene_ch1" in script
    assert "shot1.png" in script
    assert "Chapter One" in script


def test_build_manim_script_outro():
    chapter = {
        "id": "outro",
        "title": "Conclusion",
        "narration": "Thank you for watching.",
        "scene_type": "manim",
        "images": [],
        "duration_estimate": 12.0,
    }
    script = build_manim_script(
        chapter=chapter,
        doc_title="Test Documentary",
        duration=12.0,
        images_dir=Path("/fake/images"),
    )
    assert "class Scene_outro" in script
    assert "Conclusion" in script
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_render.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

`src/docugen/tools/render.py`:
```python
"""Render tool: generate Manim scenes per chapter and render to MP4."""

import json
import subprocess
import tempfile
from pathlib import Path

from scipy.io import wavfile

from docugen.config import load_config

# Palette (3Blue1Brown-inspired)
BG = "#0f0f1a"
GOLD = "#f5c518"
TEAL = "#3ec9a7"
WHITE = "#f0f0f0"
MUTED = "#888899"


def _get_wav_duration(wav_path: Path) -> float:
    """Get duration of a WAV file in seconds."""
    sr, data = wavfile.read(str(wav_path))
    if data.ndim > 1:
        data = data[:, 0]
    return len(data) / sr


def build_manim_script(chapter: dict, doc_title: str, duration: float,
                       images_dir: Path) -> str:
    """Generate a Manim Python script for a single chapter scene.

    Returns the script as a string.
    """
    cid = chapter["id"]
    title = chapter["title"]
    scene_type = chapter["scene_type"]
    images = chapter.get("images", [])
    class_name = f"Scene_{cid}"

    # Escape strings for Python source
    title_esc = title.replace('"', '\\"')
    doc_title_esc = doc_title.replace('"', '\\"')

    if cid == "intro":
        return _intro_script(class_name, doc_title_esc, title_esc, duration)
    elif cid == "outro":
        return _outro_script(class_name, doc_title_esc, title_esc, duration)
    elif scene_type == "mixed" and images:
        return _mixed_script(class_name, title_esc, duration, images, images_dir)
    else:
        return _chapter_card_script(class_name, title_esc, duration)


def _intro_script(class_name: str, doc_title: str, subtitle: str,
                  duration: float) -> str:
    return f'''\
from manim import *

config.background_color = "{BG}"

class {class_name}(Scene):
    def construct(self):
        title = Text("{doc_title}", color="{GOLD}").scale(1.2)
        subtitle = Text("{subtitle}", color="{TEAL}").scale(0.6)
        subtitle.next_to(title, DOWN, buff=0.5)

        self.play(FadeIn(title, shift=UP * 0.3), run_time=2.0)
        self.play(FadeIn(subtitle, shift=UP * 0.2), run_time=1.5)
        self.wait({max(duration - 5.0, 1.0):.1f})
        self.play(FadeOut(title), FadeOut(subtitle), run_time=1.5)
'''


def _outro_script(class_name: str, doc_title: str, title: str,
                  duration: float) -> str:
    return f'''\
from manim import *

config.background_color = "{BG}"

class {class_name}(Scene):
    def construct(self):
        title = Text("{title}", color="{GOLD}").scale(1.0)
        credit = Text("{doc_title}", color="{MUTED}").scale(0.5)
        credit.next_to(title, DOWN, buff=0.8)

        self.play(FadeIn(title, shift=UP * 0.3), run_time=2.0)
        self.play(FadeIn(credit), run_time=1.0)
        self.wait({max(duration - 6.0, 1.0):.1f})
        self.play(FadeOut(title), FadeOut(credit), run_time=2.0)
        self.wait(1.0)
'''


def _chapter_card_script(class_name: str, title: str, duration: float) -> str:
    return f'''\
from manim import *

config.background_color = "{BG}"

class {class_name}(Scene):
    def construct(self):
        title = Text("{title}", color="{WHITE}").scale(0.9)
        self.play(FadeIn(title, shift=RIGHT * 0.3), run_time=1.5)
        self.wait({max(duration - 3.0, 1.0):.1f})
        self.play(FadeOut(title), run_time=1.5)
'''


def _mixed_script(class_name: str, title: str, duration: float,
                  images: list[str], images_dir: Path) -> str:
    """Scene with chapter card + images with Ken Burns motion."""
    images_dir_str = str(images_dir).replace("\\", "\\\\")
    image_items = ", ".join(f'"{img}"' for img in images)
    time_per_image = max((duration - 4.0) / max(len(images), 1), 2.0)

    return f'''\
from manim import *
from pathlib import Path

config.background_color = "{BG}"

class {class_name}(Scene):
    def construct(self):
        images_dir = Path("{images_dir_str}")
        image_names = [{image_items}]

        # Chapter card
        title = Text("{title}", color="{WHITE}").scale(0.9)
        self.play(FadeIn(title, shift=RIGHT * 0.3), run_time=1.5)
        self.wait(0.5)
        self.play(FadeOut(title), run_time=0.5)

        # Images with Ken Burns
        for img_name in image_names:
            img_path = images_dir / img_name
            if not img_path.exists():
                continue
            img = ImageMobject(str(img_path))
            img.height = min(img.height, 6.0)
            img.width = min(img.width, 10.0)
            img.scale(0.9)

            self.play(FadeIn(img), run_time=1.0)
            # Ken Burns: slow zoom
            self.play(
                img.animate.scale(1.08),
                run_time={time_per_image:.1f},
                rate_func=linear,
            )
            self.play(FadeOut(img), run_time=0.8)
'''


def render_chapter(project_path: Path, chapter: dict, doc_title: str,
                   duration: float) -> str:
    """Render a single chapter to MP4 using Manim.

    Returns path to the rendered clip.
    """
    project_path = Path(project_path)
    config = load_config(project_path)
    cid = chapter["id"]
    images_dir = project_path / "images"
    clips_dir = project_path / "build" / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    script = build_manim_script(chapter, doc_title, duration, images_dir)
    class_name = f"Scene_{cid}"

    # Write temp script
    script_path = clips_dir / f"_scene_{cid}.py"
    script_path.write_text(script)

    # Determine quality flag
    fps = config["video"]["fps"]
    quality = "-qh" if fps >= 60 else "-qm"

    # Render
    cmd = [
        "manim", quality,
        str(script_path), class_name,
        "--media_dir", str(clips_dir / "media"),
        "--format", "mp4",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(clips_dir))
    if result.returncode != 0:
        raise RuntimeError(f"Manim render failed for {cid}:\n{result.stderr}")

    # Find the output file (Manim puts it in media/videos/...)
    output_files = list((clips_dir / "media").rglob(f"{class_name}.mp4"))
    if not output_files:
        raise FileNotFoundError(f"Manim output not found for {class_name}")

    # Copy to clips dir with clean name
    final_path = clips_dir / f"{cid}.mp4"
    output_files[0].rename(final_path)

    # Clean up temp script
    script_path.unlink(missing_ok=True)

    return str(final_path)


def render_all(project_path: str | Path) -> str:
    """Render all chapters in plan.json to individual MP4 clips.

    Returns a summary string.
    """
    project_path = Path(project_path)
    config = load_config(project_path)

    plan_path = project_path / "build" / "plan.json"
    if not plan_path.exists():
        raise FileNotFoundError("No plan.json found. Run 'plan' first.")

    plan = json.loads(plan_path.read_text())
    narration_dir = project_path / "build" / "narration"
    results = []

    for chapter in plan["chapters"]:
        cid = chapter["id"]

        # Get actual duration from narration WAV if available
        wav_path = narration_dir / f"{cid}.wav"
        if wav_path.exists():
            duration = _get_wav_duration(wav_path)
        else:
            duration = chapter.get("duration_estimate", 30.0)

        clip_path = render_chapter(project_path, chapter, plan["title"], duration)
        results.append(f"{cid}.mp4 ({duration:.1f}s)")

    return "Rendered clips:\n" + "\n".join(results)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_render.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/docugen/tools/render.py tests/test_render.py
git commit -m "feat: render tool — Manim scene generation for intro/mixed/outro chapters"
```

---

### Task 7: Stitch Tool — Audio Mixing + Video Concatenation

**Files:**
- Create: `src/docugen/tools/stitch.py`
- Create: `tests/test_stitch.py`

- [ ] **Step 1: Write the failing test**

`tests/test_stitch.py`:
```python
import json
import numpy as np
import pytest
from pathlib import Path
from scipy.io import wavfile
from unittest.mock import patch
from docugen.tools.stitch import (
    load_narration_tracks,
    mix_audio,
)


def _write_test_wav(path: Path, duration: float, sr: int = 44100, stereo: bool = False):
    """Write a silent WAV file for testing."""
    n_samples = int(duration * sr)
    if stereo:
        data = np.zeros((n_samples, 2), dtype=np.int16)
    else:
        data = np.zeros(n_samples, dtype=np.int16)
    wavfile.write(str(path), sr, data)


@pytest.fixture
def project_dir(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "title: Test\n"
        "drone:\n"
        "  cutoff_hz: 400\n"
        "  duck_db: -18\n"
        "  rt60: 1.5\n"
        "  cue_freq: 220\n"
    )
    build = tmp_path / "build"
    build.mkdir()
    narration = build / "narration"
    narration.mkdir()
    clips = build / "clips"
    clips.mkdir()

    plan = {
        "title": "Test",
        "chapters": [
            {"id": "intro", "title": "Intro", "narration": "...",
             "scene_type": "manim", "images": [], "duration_estimate": 5.0},
            {"id": "ch1", "title": "Ch1", "narration": "...",
             "scene_type": "mixed", "images": [], "duration_estimate": 10.0},
        ],
    }
    (build / "plan.json").write_text(json.dumps(plan))

    _write_test_wav(narration / "intro.wav", 5.0)
    _write_test_wav(narration / "ch1.wav", 10.0)

    return tmp_path


def test_load_narration_tracks(project_dir):
    tracks = load_narration_tracks(project_dir)
    assert "intro" in tracks
    assert "ch1" in tracks
    assert tracks["intro"]["duration"] == pytest.approx(5.0, abs=0.1)


def test_mix_audio_output_shape():
    sr = 44100
    n = sr * 10  # 10 seconds
    voice = np.zeros((n, 2))
    drone = np.random.default_rng(0).standard_normal((n, 2)) * 0.1
    mixed = mix_audio(voice, drone, duck_db=-18, sr=sr)
    assert mixed.shape == (n, 2)
    # Should not clip
    assert np.max(np.abs(mixed)) <= 1.0 + 1e-6
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_stitch.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

`src/docugen/tools/stitch.py`:
```python
"""Stitch tool: combine clips + narration + drone → final video."""

import json
import subprocess
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter

from docugen.config import load_config
from docugen.drone import generate_drone_track

SR = 44100


def db_to_amp(db: float) -> float:
    return 10.0 ** (db / 20.0)


def _read_wav_float(path: Path) -> tuple[int, np.ndarray]:
    sr, data = wavfile.read(str(path))
    if data.dtype == np.int16:
        data = data.astype(np.float64) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float64) / 2147483648.0
    elif data.dtype == np.float32:
        data = data.astype(np.float64)
    return sr, data


def _mono_to_stereo(data: np.ndarray) -> np.ndarray:
    if data.ndim == 1:
        return np.column_stack([data, data])
    return data


def _pad_or_trim(data: np.ndarray, target: int) -> np.ndarray:
    if data.shape[0] >= target:
        return data[:target]
    if data.ndim == 1:
        return np.pad(data, (0, target - data.shape[0]))
    padding = np.zeros((target - data.shape[0], data.shape[1]))
    return np.vstack([data, padding])


def load_narration_tracks(project_path: Path) -> dict:
    """Load narration WAV files and return metadata dict.

    Returns: {chapter_id: {"path": Path, "duration": float, "data": ndarray}}
    """
    project_path = Path(project_path)
    narration_dir = project_path / "build" / "narration"
    plan = json.loads((project_path / "build" / "plan.json").read_text())

    tracks = {}
    for chapter in plan["chapters"]:
        cid = chapter["id"]
        wav_path = narration_dir / f"{cid}.wav"
        if wav_path.exists():
            sr, data = _read_wav_float(wav_path)
            data = _mono_to_stereo(data)
            tracks[cid] = {
                "path": wav_path,
                "duration": data.shape[0] / sr,
                "data": data,
                "sr": sr,
            }

    return tracks


def mix_audio(voice: np.ndarray, drone: np.ndarray, duck_db: float = -18,
              sr: int = SR) -> np.ndarray:
    """Mix voice and drone with voice-activated ducking.

    Args:
        voice: Stereo voice array (N, 2).
        drone: Stereo drone array (N, 2).
        duck_db: dB attenuation of drone when voice is active.
        sr: Sample rate.

    Returns:
        Mixed stereo array (N, 2), normalized to -1dB peak.
    """
    # Compute voice RMS envelope for ducking
    mono_voice = voice.mean(axis=1) if voice.ndim > 1 else voice
    window_samples = int(0.1 * sr)  # 100ms window
    squared = mono_voice ** 2
    window = np.ones(window_samples) / window_samples
    rms = np.sqrt(np.convolve(squared, window, mode="same"))

    # Ducking envelope
    threshold = db_to_amp(-40)
    duck_amount = db_to_amp(duck_db)
    active = (rms > threshold).astype(np.float64)

    # Smooth with one-pole lowpass
    coeff = 1.0 / max(int(0.2 * sr), 1)  # 200ms attack
    b = [coeff]
    a = [1.0, -(1.0 - coeff)]
    smoothed = lfilter(b, a, active)
    smoothed = np.clip(smoothed, 0.0, 1.0)

    # Apply ducking to drone
    gain = 1.0 - smoothed * (1.0 - duck_amount)
    drone[:, 0] *= gain
    drone[:, 1] *= gain

    # Mix
    drone_level = db_to_amp(-18)
    mixed = voice + drone * drone_level

    # Normalize to -1dB peak
    peak = np.max(np.abs(mixed)) + 1e-10
    target_peak = db_to_amp(-1)
    mixed = mixed * (target_peak / peak)

    return mixed


def _concatenate_clips(project_path: Path, plan: dict) -> Path:
    """Concatenate chapter clips in order using FFmpeg."""
    clips_dir = project_path / "build" / "clips"
    build_dir = project_path / "build"

    # Write concat list
    concat_file = build_dir / "concat.txt"
    lines = []
    for chapter in plan["chapters"]:
        clip = clips_dir / f"{chapter['id']}.mp4"
        if clip.exists():
            lines.append(f"file '{clip}'")

    concat_file.write_text("\n".join(lines))

    # Concatenate
    concat_video = build_dir / "concat.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(concat_video),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg concat failed:\n{result.stderr}")

    return concat_video


def _get_video_duration(video_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def stitch_all(project_path: str | Path) -> str:
    """Stitch clips + narration + drone into final video.

    Returns summary string with path to final.mp4.
    """
    project_path = Path(project_path)
    config = load_config(project_path)
    drone_config = config["drone"]
    build_dir = project_path / "build"

    plan = json.loads((build_dir / "plan.json").read_text())

    # 1. Concatenate video clips
    concat_video = _concatenate_clips(project_path, plan)
    video_duration = _get_video_duration(concat_video)

    # 2. Assemble narration into continuous track
    tracks = load_narration_tracks(project_path)
    total_samples = int(video_duration * SR)
    voice_full = np.zeros((total_samples, 2))

    offset = 0.0
    chapter_start_times = []
    for chapter in plan["chapters"]:
        cid = chapter["id"]
        chapter_start_times.append(offset)
        if cid in tracks:
            track_data = tracks[cid]["data"]
            start_sample = int(offset * SR)
            end_sample = min(start_sample + track_data.shape[0], total_samples)
            actual_len = end_sample - start_sample
            voice_full[start_sample:end_sample] = track_data[:actual_len]
            offset += tracks[cid]["duration"]
        else:
            offset += chapter.get("duration_estimate", 10.0)

    # 3. Generate drone
    drone = generate_drone_track(
        total_duration=video_duration,
        chapter_start_times=chapter_start_times,
        cutoff_hz=drone_config["cutoff_hz"],
        cue_freq=drone_config["cue_freq"],
        rt60=drone_config["rt60"],
        sr=SR,
    )
    drone = _pad_or_trim(drone, total_samples)

    # 4. Mix audio
    mixed = mix_audio(voice_full, drone, duck_db=drone_config["duck_db"], sr=SR)

    # 5. Write mixed audio WAV
    mixed_wav = build_dir / "mixed_audio.wav"
    output_16 = np.clip(mixed * 32767, -32768, 32767).astype(np.int16)
    wavfile.write(str(mixed_wav), SR, output_16)

    # 6. Merge audio onto video
    final_path = build_dir / "final.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-i", str(concat_video),
        "-i", str(mixed_wav),
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(final_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg merge failed:\n{result.stderr}")

    # Cleanup
    (build_dir / "concat.txt").unlink(missing_ok=True)
    concat_video.unlink(missing_ok=True)

    return f"Final video: {final_path} ({video_duration:.1f}s)"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_stitch.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/docugen/tools/stitch.py tests/test_stitch.py
git commit -m "feat: stitch tool — audio mixing, drone synthesis, video concatenation"
```

---

### Task 8: MCP Server

**Files:**
- Create: `src/docugen/server.py`

- [ ] **Step 1: Write the server**

`src/docugen/server.py`:
```python
"""Docugen MCP Server — documentary generation pipeline."""

from mcp.server.fastmcp import FastMCP

from docugen.tools.plan import extract_pdf_text, generate_plan
from docugen.tools.narrate import generate_narration
from docugen.tools.render import render_all
from docugen.tools.stitch import stitch_all

mcp = FastMCP("docugen", instructions=(
    "Documentary generation pipeline. Use tools in order: "
    "plan → narrate → render → stitch. "
    "Review artifacts between stages."
))


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
def narrate(project_path: str) -> str:
    """Generate TTS narration audio for each chapter in plan.json.

    Requires: build/plan.json (run 'plan' first).
    Creates: build/narration/*.wav (one per chapter).

    Uses OpenAI tts-1-hd with echo voice. Automatically adjusts
    speed if narration exceeds chapter duration estimate.

    Args:
        project_path: Path to project directory.
    """
    return generate_narration(project_path)


@mcp.tool()
def render(project_path: str) -> str:
    """Render Manim video scenes for each chapter.

    Requires: build/plan.json and build/narration/*.wav.
    Creates: build/clips/*.mp4 (one per chapter).

    Intro/outro get animated title cards. Mixed chapters get
    chapter cards + images with Ken Burns motion.

    Args:
        project_path: Path to project directory.
    """
    return render_all(project_path)


@mcp.tool()
def stitch(project_path: str) -> str:
    """Combine all clips, narration, and drone audio into final video.

    Requires: build/clips/*.mp4 and build/narration/*.wav.
    Creates: build/final.mp4.

    Synthesizes ambient drone with chapter transition cues,
    applies voice-activated ducking, and merges everything.

    Args:
        project_path: Path to project directory.
    """
    return stitch_all(project_path)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add entry point to pyproject.toml**

Add to `pyproject.toml`:
```toml
[project.scripts]
docugen = "docugen.server:main"
```

- [ ] **Step 3: Verify server starts**

```bash
cd /Users/crashy/Development/docu-mentation
source .venv/bin/activate
python -m docugen.server &
# Should start without errors, then kill it
kill %1
```

- [ ] **Step 4: Commit**

```bash
git add src/docugen/server.py pyproject.toml
git commit -m "feat: MCP server with plan/narrate/render/stitch tools"
```

---

### Task 9: MCP Registration + Integration Test

**Files:**
- Modify: `pyproject.toml` (add MCP config hint)

- [ ] **Step 1: Test MCP server can be listed**

```bash
cd /Users/crashy/Development/docu-mentation
source .venv/bin/activate
pip install -e ".[dev]"
python -c "from docugen.server import mcp; print(mcp.name)"
```

Expected: `docugen`

- [ ] **Step 2: Run full test suite**

```bash
pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 3: Add MCP server to Claude Code settings**

Add to `~/.claude/settings.json` (or project `.claude/settings.json`):
```json
{
  "mcpServers": {
    "docugen": {
      "type": "stdio",
      "command": "/Users/crashy/Development/docu-mentation/.venv/bin/python",
      "args": ["-m", "docugen.server"]
    }
  }
}
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: MCP registration and integration verification"
```

---

### Task 10: Final Verification

- [ ] **Step 1: Verify project structure matches spec**

```bash
cd /Users/crashy/Development/docu-mentation
find src tests projects -type f | sort
```

Expected output should match the file structure from the spec.

- [ ] **Step 2: Verify all tests pass**

```bash
source .venv/bin/activate
pytest tests/ -v --tb=short
```

Expected: All tests pass.

- [ ] **Step 3: Verify imports work end-to-end**

```bash
python -c "
from docugen.config import load_config
from docugen.tools.plan import extract_pdf_text, generate_plan, list_images
from docugen.tools.narrate import generate_narration
from docugen.tools.render import render_all, build_manim_script
from docugen.tools.stitch import stitch_all, mix_audio
from docugen.drone import generate_drone_track, pink_noise
from docugen.server import mcp
print('All imports OK')
print(f'MCP tools: {[t.name for t in mcp._tool_manager.list_tools()]}')
"
```

Expected: `All imports OK` and lists all 4 tools.

- [ ] **Step 4: Commit any final fixes**

```bash
git log --oneline
```

Verify clean commit history.
