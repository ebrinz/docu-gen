# Audio-First Pipeline & Storyboard Gate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the docugen pipeline so narration audio is the authoritative timeline: every rendered clip has duration exactly equal to its audio slot. Add a pre-render storyboard review, auto-wire the title card, diversify chapter openers, and move short-emotive narration bans upstream to the plan stage.

**Architecture:** Three new MCP tools (`base_clips`, `storyboard_preview`, `composite`) insert between `narrate` and `render`. `base_clips` emits a silent black MP4 per clip at exact `clip_duration`. `storyboard_preview` burns clip_id + content tag + subtitle onto those base clips for reviewer approval. After Manim `render`, `composite` overlays the Manim output onto the base clip and forces `-t clip_duration`, making drift impossible. `plan_apply` gains a short-emotive-ban validator; `direct_prepare` gains a `prior_directions` context field; `stitch` auto-invokes `title` if no title.mp4 exists.

**Tech Stack:** Python 3.11+, FastMCP, ffmpeg (CLI via subprocess), Manim, Chatterbox (MLX TTS), pytest, scipy.io.wavfile.

**Spec:** `docs/superpowers/specs/2026-04-18-audio-first-pipeline-design.md`

---

## File Structure

**New files:**
- `src/docugen/tools/base_clips.py` — audio-bound base MP4 generator
- `src/docugen/tools/storyboard.py` — storyboard preview composer
- `src/docugen/tools/composite.py` — Manim-on-base overlay with duration enforcement
- `tests/test_base_clips.py`
- `tests/test_storyboard.py`
- `tests/test_composite.py`
- `tests/test_plan_short_emotive.py` — short-emotive ban tests
- `tests/fixtures/short_emotive_project/` — fixture for ban tests
- `tests/fixtures/minimal_clips_project/` — fixture for base_clips/composite tests

**Modified files:**
- `src/docugen/tools/plan.py` — add `_validate_short_emotive` called from `plan_apply`
- `src/docugen/direct.py` — `prepare_direction_context` adds `prior_directions` per clip; `apply_direction` warns on three-consecutive-same primitive/reveal
- `src/docugen/tools/stitch.py` — auto-invoke `title` if `build/title.mp4` missing; prepend to concat
- `src/docugen/server.py` — register `base_clips`, `storyboard_preview`, `composite` MCP tools; update instructions string
- `src/docugen/tools/render.py` — pass `clip_duration` hint into scene builders; emit to `build/frames/<id>.mp4` instead of `build/clips/<id>.mp4`

**Tests added for modified files:**
- `tests/test_plan_short_emotive.py`
- Add cases to existing `tests/test_direct.py` for `prior_directions` and variety warning
- Add case to existing `tests/test_stitch.py` for title auto-invocation

---

## Task Breakdown

Tasks are ordered so each leaves the repo in a green state. New tools come first (isolated, tested standalone), then wiring into the pipeline, then upstream validators, then renderer path change. The renderer path change comes last because it requires the composite step to already exist.

---

### Task 1: `base_clips` tool — silent black MP4 per clip

**Files:**
- Create: `src/docugen/tools/base_clips.py`
- Create: `tests/test_base_clips.py`
- Create: `tests/fixtures/minimal_clips_project/build/clips.json`
- Create: `tests/fixtures/minimal_clips_project/config.yaml`

- [ ] **Step 1: Create fixture project**

Create `tests/fixtures/minimal_clips_project/config.yaml`:

```yaml
title: "Fixture Project"
video:
  resolution: 1080p
  fps: 60
voice:
  model: tts-1-hd
  voice: fable
```

Create `tests/fixtures/minimal_clips_project/build/clips.json`:

```json
{
  "chapters": [
    {
      "id": "intro",
      "clips": [
        {"clip_id": "intro_01", "text": "Hello world.", "timing": {"clip_duration": 2.5}},
        {"clip_id": "intro_02", "text": "", "timing": {"clip_duration": 3.0}}
      ]
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_base_clips.py`:

```python
"""Tests for base_clips tool."""
import subprocess
import shutil
from pathlib import Path
import pytest

from docugen.tools.base_clips import generate_base_clips


FIXTURE_SRC = Path(__file__).parent / "fixtures" / "minimal_clips_project"


@pytest.fixture
def project(tmp_path):
    dest = tmp_path / "proj"
    shutil.copytree(FIXTURE_SRC, dest)
    return dest


def _probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def test_generates_one_mp4_per_clip(project):
    generate_base_clips(project)
    base_dir = project / "build" / "base"
    assert (base_dir / "intro_01.mp4").exists()
    assert (base_dir / "intro_02.mp4").exists()


def test_duration_matches_clip_duration(project):
    generate_base_clips(project)
    base_dir = project / "build" / "base"
    assert _probe_duration(base_dir / "intro_01.mp4") == pytest.approx(2.5, abs=0.05)
    assert _probe_duration(base_dir / "intro_02.mp4") == pytest.approx(3.0, abs=0.05)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_base_clips.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'docugen.tools.base_clips'`

- [ ] **Step 4: Implement `base_clips.py`**

Create `src/docugen/tools/base_clips.py`:

```python
"""Base clip generator: silent black MP4 per clip at exact clip_duration.

The base clip becomes the duration contract. Manim render is composited on top;
the composite step forces ffmpeg -t clip_duration so drift cannot escape.
"""

import json
import subprocess
from pathlib import Path

from docugen.config import load_config


_RESOLUTIONS = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "1440p": (2560, 1440),
    "4k": (3840, 2160),
}


def _resolve_wh(config: dict) -> tuple[int, int]:
    res = config.get("video", {}).get("resolution", "1080p")
    if res in _RESOLUTIONS:
        return _RESOLUTIONS[res]
    if "x" in str(res):
        w, h = str(res).lower().split("x")
        return int(w), int(h)
    raise ValueError(f"Unknown resolution: {res}")


def _build_one(out_path: Path, width: int, height: int, fps: int, duration: float) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=black:s={width}x{height}:r={fps}",
        "-t", f"{duration:.6f}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-an",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"base_clips ffmpeg failed for {out_path.name}:\n{result.stderr}"
        )


def generate_base_clips(project_path: str | Path) -> str:
    """Generate one silent black MP4 per clip at exact clip_duration.

    Reads build/clips.json; writes build/base/<clip_id>.mp4 for every clip
    whose timing.clip_duration > 0.
    """
    project_path = Path(project_path)
    config = load_config(project_path)
    width, height = _resolve_wh(config)
    fps = int(config.get("video", {}).get("fps", 30))

    clips_data = json.loads((project_path / "build" / "clips.json").read_text())
    base_dir = project_path / "build" / "base"
    base_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for chapter in clips_data["chapters"]:
        for clip in chapter["clips"]:
            clip_id = clip["clip_id"]
            duration = clip.get("timing", {}).get("clip_duration", 0)
            if duration <= 0:
                continue
            out_path = base_dir / f"{clip_id}.mp4"
            _build_one(out_path, width, height, fps, duration)
            count += 1

    return f"base_clips: wrote {count} base MP4s to {base_dir}"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_base_clips.py -v`
Expected: both tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/docugen/tools/base_clips.py tests/test_base_clips.py tests/fixtures/minimal_clips_project/
git commit -m "feat: base_clips tool generates silent black MP4 per clip at exact duration"
```

---

### Task 2: Register `base_clips` as MCP tool

**Files:**
- Modify: `src/docugen/server.py`
- Test: `tests/test_base_clips.py` (add MCP registration smoke test)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_base_clips.py`:

```python
def test_base_clips_registered_as_mcp_tool():
    from docugen import server
    tool_names = [t.name for t in server.mcp._tool_manager.list_tools()]
    assert "base_clips" in tool_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_base_clips.py::test_base_clips_registered_as_mcp_tool -v`
Expected: FAIL — `"base_clips" not in tool_names`

- [ ] **Step 3: Register tool in server.py**

Modify `src/docugen/server.py`. After the existing `from docugen.tools.title import generate_title` import, add:

```python
from docugen.tools.base_clips import generate_base_clips
```

Then add this tool registration after the existing `title` MCP tool registration (near the end of the tool section):

```python
@mcp.tool()
def base_clips(project_path: str) -> str:
    """Generate silent black MP4 per clip at exact clip_duration.

    Reads build/clips.json and emits build/base/<clip_id>.mp4 for every clip.
    These base clips are the duration contract for composite; Manim renders
    are overlayed onto them.

    Args:
        project_path: Path to project directory.
    """
    return generate_base_clips(project_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_base_clips.py -v`
Expected: all three tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/docugen/server.py tests/test_base_clips.py
git commit -m "feat: register base_clips MCP tool"
```

---

### Task 3: `storyboard_preview` tool — concat base + overlay text + mux narration

**Files:**
- Create: `src/docugen/tools/storyboard.py`
- Create: `tests/test_storyboard.py`
- Modify: `tests/fixtures/minimal_clips_project/` (add sample WAV)

- [ ] **Step 1: Add narration WAV fixture**

Generate a short silent-ish placeholder WAV for fixtures:

```bash
mkdir -p tests/fixtures/minimal_clips_project/build/narration
ffmpeg -y -f lavfi -i "sine=frequency=200:duration=2.0" -ar 44100 -ac 1 \
  tests/fixtures/minimal_clips_project/build/narration/intro_01.wav
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_storyboard.py`:

```python
"""Tests for storyboard_preview tool."""
import shutil
import subprocess
from pathlib import Path
import pytest

from docugen.tools.base_clips import generate_base_clips
from docugen.tools.storyboard import generate_storyboard_preview


FIXTURE_SRC = Path(__file__).parent / "fixtures" / "minimal_clips_project"


@pytest.fixture
def project(tmp_path):
    dest = tmp_path / "proj"
    shutil.copytree(FIXTURE_SRC, dest)
    generate_base_clips(dest)
    return dest


def _probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def test_generates_storyboard_mp4(project):
    generate_storyboard_preview(project)
    assert (project / "build" / "storyboard.mp4").exists()


def test_storyboard_duration_equals_sum_of_clip_durations(project):
    generate_storyboard_preview(project)
    storyboard = project / "build" / "storyboard.mp4"
    # fixture: intro_01 = 2.5s, intro_02 = 3.0s, sum = 5.5s
    assert _probe_duration(storyboard) == pytest.approx(5.5, abs=0.2)


def test_storyboard_handles_silent_clip_without_wav(project):
    # intro_02 has no narration WAV; should not error
    generate_storyboard_preview(project)
    assert (project / "build" / "storyboard.mp4").exists()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_storyboard.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'docugen.tools.storyboard'`

- [ ] **Step 4: Implement `storyboard.py`**

Create `src/docugen/tools/storyboard.py`:

```python
"""Storyboard preview: burn clip id + content tag + subtitle onto base clips.

Run after base_clips. Produces build/storyboard.mp4 for end-to-end timing
review before any Manim rendering cost is paid.
"""

import json
import shlex
import subprocess
import textwrap
from pathlib import Path


def _content_tag(clip: dict) -> str:
    """Compact descriptor pulled from clip fields for the storyboard card."""
    parts = []
    scene_type = clip.get("scene_type")
    if scene_type:
        parts.append(scene_type)
    primitive = clip.get("primitive") or clip.get("diagram_type")
    if primitive:
        parts.append(primitive)
    assets = clip.get("images") or clip.get("assets") or []
    if assets:
        parts.append(" · ".join(assets))
    return " · ".join(parts) if parts else "(no visual direction)"


def _escape_drawtext(s: str) -> str:
    """Escape for ffmpeg drawtext filter."""
    return (
        s.replace("\\", "\\\\")
         .replace(":", "\\:")
         .replace("'", "\u2019")
         .replace("%", "\\%")
    )


def _wrap(text: str, width: int) -> str:
    return "\n".join(textwrap.wrap(text, width=width)) if text else ""


def _build_overlay_filter(clip_index: int, clip: dict) -> str:
    """Construct drawtext filter chain for one clip's storyboard card."""
    header = f"CLIP {clip_index:02d} / {clip['clip_id']}"
    tag = _content_tag(clip)
    subtitle = _wrap(clip.get("text", ""), 70)

    layers = [
        f"drawtext=text='{_escape_drawtext(header)}':"
        f"fontcolor=white:fontsize=36:x=60:y=60",
        f"drawtext=text='{_escape_drawtext(tag)}':"
        f"fontcolor=#f5c518:fontsize=28:x=60:y=120",
    ]
    if subtitle:
        layers.append(
            f"drawtext=text='{_escape_drawtext(subtitle)}':"
            f"fontcolor=white:fontsize=32:x=60:y=h-120-text_h"
        )
    return ",".join(layers)


def _render_overlay_clip(base_path: Path, narration_path: Path | None,
                         filter_chain: str, out_path: Path) -> None:
    inputs = ["-i", str(base_path)]
    if narration_path and narration_path.exists():
        inputs += ["-i", str(narration_path)]
        audio_map = ["-map", "1:a"]
    else:
        audio_map = ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                     "-map", "2:a"]
        inputs += []  # the anullsrc input is appended below

    cmd = ["ffmpeg", "-y", *inputs]
    if not (narration_path and narration_path.exists()):
        cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
    cmd += [
        "-vf", filter_chain,
        "-map", "0:v",
        *audio_map,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"storyboard_preview ffmpeg failed for {out_path.name}:\n{result.stderr}"
        )


def _concat_ts(ts_paths: list[Path], out_path: Path) -> None:
    concat_arg = "concat:" + "|".join(str(p) for p in ts_paths)
    subprocess.run(
        ["ffmpeg", "-y", "-i", concat_arg,
         "-c", "copy", "-bsf:a", "aac_adtstoasc",
         str(out_path)],
        capture_output=True, text=True, check=True,
    )


def generate_storyboard_preview(project_path: str | Path) -> str:
    """Emit build/storyboard.mp4 — base clips with clip id, tag, subtitle overlay."""
    project_path = Path(project_path)
    build = project_path / "build"
    base_dir = build / "base"
    narr_dir = build / "narration"
    work_dir = build / "_storyboard"
    work_dir.mkdir(parents=True, exist_ok=True)

    clips_data = json.loads((build / "clips.json").read_text())

    ts_paths = []
    index = 0
    for chapter in clips_data["chapters"]:
        for clip in chapter["clips"]:
            index += 1
            clip_id = clip["clip_id"]
            base_path = base_dir / f"{clip_id}.mp4"
            if not base_path.exists():
                continue
            narr_path = narr_dir / f"{clip_id}.wav"
            overlay_mp4 = work_dir / f"{clip_id}.mp4"
            _render_overlay_clip(
                base_path,
                narr_path if narr_path.exists() else None,
                _build_overlay_filter(index, clip),
                overlay_mp4,
            )
            ts_path = work_dir / f"{clip_id}.ts"
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(overlay_mp4),
                 "-c", "copy", "-bsf:v", "h264_mp4toannexb",
                 "-f", "mpegts", str(ts_path)],
                capture_output=True, text=True, check=True,
            )
            ts_paths.append(ts_path)

    if not ts_paths:
        raise RuntimeError("storyboard_preview: no base clips found; run base_clips first")

    out_path = build / "storyboard.mp4"
    _concat_ts(ts_paths, out_path)

    for p in work_dir.iterdir():
        p.unlink()
    work_dir.rmdir()

    return f"storyboard_preview: wrote {out_path}"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_storyboard.py -v`
Expected: all three tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/docugen/tools/storyboard.py tests/test_storyboard.py tests/fixtures/minimal_clips_project/build/narration/
git commit -m "feat: storyboard_preview tool for pre-render timing review"
```

---

### Task 4: Register `storyboard_preview` as MCP tool

**Files:**
- Modify: `src/docugen/server.py`
- Test: `tests/test_storyboard.py` (add registration test)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_storyboard.py`:

```python
def test_storyboard_registered_as_mcp_tool():
    from docugen import server
    tool_names = [t.name for t in server.mcp._tool_manager.list_tools()]
    assert "storyboard_preview" in tool_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storyboard.py::test_storyboard_registered_as_mcp_tool -v`
Expected: FAIL

- [ ] **Step 3: Add registration to server.py**

Add import next to the `base_clips` import:

```python
from docugen.tools.storyboard import generate_storyboard_preview
```

Add tool registration after `base_clips`:

```python
@mcp.tool()
def storyboard_preview(project_path: str) -> str:
    """Generate build/storyboard.mp4 — base clips + clip id + content tag + subtitle.

    Run after base_clips to review timing, pacing, and silent-card durations
    end-to-end before spending compute on Manim rendering.

    Args:
        project_path: Path to project directory.
    """
    return generate_storyboard_preview(project_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storyboard.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/docugen/server.py tests/test_storyboard.py
git commit -m "feat: register storyboard_preview MCP tool"
```

---

### Task 5: `composite` tool — overlay Manim on base, force duration

**Files:**
- Create: `src/docugen/tools/composite.py`
- Create: `tests/test_composite.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_composite.py`:

```python
"""Tests for composite tool."""
import shutil
import subprocess
from pathlib import Path
import pytest

from docugen.tools.base_clips import generate_base_clips
from docugen.tools.composite import composite_all


FIXTURE_SRC = Path(__file__).parent / "fixtures" / "minimal_clips_project"


def _probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def _make_fake_manim(path: Path, duration: float, width=1920, height=1080, fps=60):
    """Emit a red solid MP4 to stand in for a Manim render."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"color=c=red:s={width}x{height}:r={fps}",
         "-t", f"{duration}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(path)],
        capture_output=True, text=True, check=True,
    )


@pytest.fixture
def project(tmp_path):
    dest = tmp_path / "proj"
    shutil.copytree(FIXTURE_SRC, dest)
    generate_base_clips(dest)
    frames = dest / "build" / "frames"
    # intro_01: Manim overruns base (4s vs 2.5s — must be trimmed)
    _make_fake_manim(frames / "intro_01.mp4", 4.0)
    # intro_02: Manim underruns base (1s vs 3s — base black shows after)
    _make_fake_manim(frames / "intro_02.mp4", 1.0)
    return dest


def test_composite_output_duration_equals_clip_duration_when_manim_overruns(project):
    composite_all(project)
    out = project / "build" / "clips" / "intro_01.mp4"
    assert out.exists()
    assert _probe_duration(out) == pytest.approx(2.5, abs=0.05)


def test_composite_output_duration_equals_clip_duration_when_manim_underruns(project):
    composite_all(project)
    out = project / "build" / "clips" / "intro_02.mp4"
    assert out.exists()
    assert _probe_duration(out) == pytest.approx(3.0, abs=0.05)


def test_composite_raises_on_duration_mismatch_beyond_tolerance(project, monkeypatch):
    """If ffmpeg somehow produces a mismatched output, composite must raise."""
    from docugen.tools import composite as cmod

    original = cmod._probe_duration
    def fake_probe(path):
        return 999.0
    monkeypatch.setattr(cmod, "_probe_duration", fake_probe)

    with pytest.raises(RuntimeError, match="duration mismatch"):
        composite_all(project)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_composite.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'docugen.tools.composite'`

- [ ] **Step 3: Implement `composite.py`**

Create `src/docugen/tools/composite.py`:

```python
"""Composite tool: overlay Manim render on base clip + mux narration.

Forces output duration = clip.timing.clip_duration via ffmpeg -t. Assertion
on the output duration provides belt-and-suspenders against drift.
"""

import json
import subprocess
from pathlib import Path


DURATION_TOLERANCE_SEC = 0.05


def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def _composite_one(base: Path, manim: Path, narration: Path | None,
                   clip_duration: float, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    inputs = ["-i", str(base), "-i", str(manim)]
    filter_complex = "[0:v][1:v]overlay=shortest=0[v]"

    if narration and narration.exists():
        inputs += ["-i", str(narration)]
        maps = ["-map", "[v]", "-map", "2:a"]
    else:
        # synthesize silence at the full clip duration
        inputs += ["-f", "lavfi", "-i",
                   f"anullsrc=channel_layout=stereo:sample_rate=44100:duration={clip_duration}"]
        maps = ["-map", "[v]", "-map", "2:a"]

    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", filter_complex,
        *maps,
        "-t", f"{clip_duration:.6f}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"composite ffmpeg failed for {out_path.name}:\n{result.stderr}"
        )

    actual = _probe_duration(out_path)
    if abs(actual - clip_duration) > DURATION_TOLERANCE_SEC:
        raise RuntimeError(
            f"composite: duration mismatch on {out_path.name}: "
            f"expected {clip_duration:.3f}s, got {actual:.3f}s"
        )


def composite_all(project_path: str | Path) -> str:
    """Composite Manim frames + narration onto base clips. Emits build/clips/<id>.mp4."""
    project_path = Path(project_path)
    build = project_path / "build"
    base_dir = build / "base"
    frames_dir = build / "frames"
    narr_dir = build / "narration"
    clips_dir = build / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    clips_data = json.loads((build / "clips.json").read_text())

    count = 0
    for chapter in clips_data["chapters"]:
        for clip in chapter["clips"]:
            clip_id = clip["clip_id"]
            clip_duration = clip.get("timing", {}).get("clip_duration", 0)
            if clip_duration <= 0:
                continue
            base = base_dir / f"{clip_id}.mp4"
            manim = frames_dir / f"{clip_id}.mp4"
            if not base.exists():
                raise FileNotFoundError(f"composite: missing base {base}")
            if not manim.exists():
                raise FileNotFoundError(f"composite: missing frames {manim}")
            narration = narr_dir / f"{clip_id}.wav"
            out_path = clips_dir / f"{clip_id}.mp4"
            _composite_one(base, manim,
                           narration if narration.exists() else None,
                           clip_duration, out_path)
            count += 1

    return f"composite: wrote {count} clips to {clips_dir}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_composite.py -v`
Expected: all three tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/docugen/tools/composite.py tests/test_composite.py
git commit -m "feat: composite tool overlays Manim on base, enforces clip duration"
```

---

### Task 6: Register `composite` as MCP tool

**Files:**
- Modify: `src/docugen/server.py`
- Test: `tests/test_composite.py` (add registration test)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_composite.py`:

```python
def test_composite_registered_as_mcp_tool():
    from docugen import server
    tool_names = [t.name for t in server.mcp._tool_manager.list_tools()]
    assert "composite" in tool_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_composite.py::test_composite_registered_as_mcp_tool -v`
Expected: FAIL

- [ ] **Step 3: Register tool**

Add import:

```python
from docugen.tools.composite import composite_all
```

Add registration:

```python
@mcp.tool()
def composite(project_path: str) -> str:
    """Overlay Manim renders onto base clips, mux narration, force duration.

    Reads build/base/<id>.mp4 + build/frames/<id>.mp4 + build/narration/<id>.wav,
    writes build/clips/<id>.mp4 with duration = clip.timing.clip_duration.

    Args:
        project_path: Path to project directory.
    """
    return composite_all(project_path)
```

Also update the `FastMCP` `instructions` string at module top to reflect the new pipeline order:

Find:
```
"init -> plan_prepare -> plan_apply -> split -> narrate -> viz_extract -> "
"direct_prepare -> direct_apply -> spot -> render -> score -> stitch. "
```

Replace with:
```
"init -> plan_prepare -> plan_apply -> split -> narrate -> "
"base_clips -> storyboard_preview (review gate) -> "
"viz_extract -> direct_prepare -> direct_apply -> spot -> render -> "
"composite -> score -> stitch. "
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_composite.py tests/test_base_clips.py tests/test_storyboard.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/docugen/server.py tests/test_composite.py
git commit -m "feat: register composite MCP tool and update pipeline instructions"
```

---

### Task 7: Short-emotive ban validator in `plan_apply`

**Files:**
- Modify: `src/docugen/tools/plan.py`
- Create: `tests/test_plan_short_emotive.py`

This validator bans clips that combine `word_count ≤ SHORT_WORD_CEIL` with `exaggeration ≥ HOT_EXAGGERATION_FLOOR`. Thresholds match the calibration constants already in `narrate.py` (`SHORT_WORD_LIMIT = 1`, `HIGH_EXAGGERATION = 0.3`) so the upstream ban matches what the downstream consolidator catches. Spec open-question asked user to confirm — use the same values as `narrate.py` and let the user tune later in one place.

- [ ] **Step 1: Write the failing test**

Create `tests/test_plan_short_emotive.py`:

```python
"""Tests for plan_apply short-emotive ban."""
import json
import pytest
from docugen.tools.plan import _validate_short_emotive, plan_apply


def _mk_chapter(cid, narration, exaggeration=None):
    ch = {
        "id": cid,
        "title": cid.title(),
        "narration": narration,
        "scene_type": "manim",
        "images": [],
        "duration_estimate": 10.0,
    }
    if exaggeration is not None:
        ch["exaggeration"] = exaggeration
    return ch


def test_long_emotive_is_allowed():
    plan = {
        "title": "T",
        "chapters": [
            _mk_chapter("intro", "This is a nice long emotive phrase that Chatterbox handles fine.", exaggeration=0.7),
            _mk_chapter("outro", "Another long one to close.", exaggeration=0.5),
        ],
    }
    assert _validate_short_emotive(plan) == []


def test_short_hot_clip_is_rejected():
    plan = {
        "title": "T",
        "chapters": [
            _mk_chapter("intro", "Wow!", exaggeration=0.6),
            _mk_chapter("outro", "A full sentence that closes out the piece nicely.", exaggeration=0.4),
        ],
    }
    errors = _validate_short_emotive(plan)
    assert len(errors) == 1
    assert "intro" in errors[0]
    assert "1 word" in errors[0] or "1-word" in errors[0]


def test_short_clip_at_low_exaggeration_is_allowed():
    plan = {
        "title": "T",
        "chapters": [
            _mk_chapter("intro", "Yes.", exaggeration=0.1),
            _mk_chapter("outro", "Full sentence goes here as the closer.", exaggeration=0.3),
        ],
    }
    assert _validate_short_emotive(plan) == []


def test_multiple_violations_all_reported():
    plan = {
        "title": "T",
        "chapters": [
            _mk_chapter("intro", "Wow!", exaggeration=0.6),
            _mk_chapter("ch1", "Full sentence.", exaggeration=0.3),
            _mk_chapter("outro", "Yes!", exaggeration=0.5),
        ],
    }
    errors = _validate_short_emotive(plan)
    assert len(errors) == 2


def test_plan_apply_refuses_short_hot_plan(tmp_path):
    (tmp_path / "build").mkdir()
    (tmp_path / "config.yaml").write_text("title: T\n")
    plan = {
        "title": "T",
        "chapters": [
            _mk_chapter("intro", "Wow!", exaggeration=0.6),
            _mk_chapter("outro", "Full closing sentence.", exaggeration=0.3),
        ],
    }
    result = plan_apply(tmp_path, json.dumps(plan))
    assert "short-emotive ban" in result.lower() or "short + emotive" in result.lower()
    assert not (tmp_path / "build" / "plan.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_plan_short_emotive.py -v`
Expected: FAIL — `ImportError: cannot import name '_validate_short_emotive'`

- [ ] **Step 3: Implement validator**

Modify `src/docugen/tools/plan.py`. Add constants and validator near the top of the file (after imports, before `PLAN_SCHEMA_PROMPT`):

```python
# Chatterbox short-emotive ban — upstream mirror of narrate.py's
# SHORT_WORD_LIMIT / HIGH_EXAGGERATION. Values derived from
# scripts/calibrate_chatterbox.py sweep against robo.flac. Tune both
# constants together (here and in narrate.py) if the calibration changes.
SHORT_WORD_CEIL = 1
HOT_EXAGGERATION_FLOOR = 0.3


def _chapter_exaggeration(chapter: dict) -> float | None:
    """Resolve a chapter's exaggeration override, if any."""
    return chapter.get("exaggeration")


def _validate_short_emotive(plan: dict) -> list[str]:
    """Reject chapters that combine short narration with high exaggeration.

    Chatterbox calibration shows 1-word clips at exaggeration ≥ 0.3 are a
    reliable failure mode. Ban at plan time rather than consolidate downstream
    so the author fixes the narration.
    """
    errors = []
    for ch in plan.get("chapters", []):
        text = ch.get("narration", "")
        word_count = len(text.split())
        exagg = _chapter_exaggeration(ch)
        if exagg is None:
            continue
        if word_count <= SHORT_WORD_CEIL and exagg >= HOT_EXAGGERATION_FLOOR:
            errors.append(
                f"chapter '{ch.get('id','?')}' violates short-emotive ban: "
                f"{word_count} word(s) at exaggeration {exagg:.2f} "
                f"(ceiling {SHORT_WORD_CEIL} words, floor {HOT_EXAGGERATION_FLOOR:.2f}). "
                f"Lengthen narration or drop exaggeration below {HOT_EXAGGERATION_FLOOR:.2f}."
            )
    return errors
```

Then modify `plan_apply` to call the validator. Find the existing validation block:

```python
    errors = _validate_plan(plan)
    if errors:
        error_list = "\n".join(f"  - {e}" for e in errors)
        return f"plan_apply: validation failed:\n{error_list}"
```

Replace with:

```python
    errors = _validate_plan(plan)
    short_emotive_errors = _validate_short_emotive(plan)
    if errors or short_emotive_errors:
        all_errors = errors + short_emotive_errors
        error_list = "\n".join(f"  - {e}" for e in all_errors)
        prefix = "plan_apply: validation failed"
        if short_emotive_errors and not errors:
            prefix = "plan_apply: short-emotive ban violations"
        return f"{prefix}:\n{error_list}"
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_plan_short_emotive.py -v`
Expected: all five tests PASS

Also run existing plan tests to confirm no regression:
Run: `pytest tests/test_plan.py -v`
Expected: all existing tests still PASS

- [ ] **Step 5: Commit**

```bash
git add src/docugen/tools/plan.py tests/test_plan_short_emotive.py
git commit -m "feat: plan_apply bans short-emotive narration upstream"
```

---

### Task 8: `prior_directions` context in `direct_prepare`

**Files:**
- Modify: `src/docugen/direct.py`
- Modify: `tests/test_direct_prepare_v2.py` (add prior_directions test)

- [ ] **Step 1: Inspect current direct_prepare**

Run: `grep -n "def prepare_direction_context\|def direct_prepare" src/docugen/direct.py`
Read the current implementation of the context-building function so the new field slots in at the right location.

- [ ] **Step 2: Write the failing test**

Append to `tests/test_direct_prepare_v2.py`:

```python
def test_prior_directions_included_in_per_clip_context(tmp_path):
    """Each clip's context must include summaries of preceding clips' direction."""
    from docugen.direct import prepare_direction_context

    # Minimal project with three clips; first two have direction, third doesn't
    (tmp_path / "build").mkdir()
    (tmp_path / "config.yaml").write_text("title: T\n")
    (tmp_path / "prompt.txt").write_text("prompt\n")
    (tmp_path / "build" / "plan.json").write_text('{"title":"T","chapters":[]}')

    clips = {
        "chapters": [{
            "id": "ch1",
            "clips": [
                {"clip_id": "ch1_01", "text": "a", "direction": {"slide_type": "banner_intro"}},
                {"clip_id": "ch1_02", "text": "b", "direction": {"slide_type": "photo_organism"}},
                {"clip_id": "ch1_03", "text": "c"},
            ],
        }]
    }
    import json
    (tmp_path / "build" / "clips.json").write_text(json.dumps(clips))

    ctx = prepare_direction_context(tmp_path)
    # The third clip's section must reference the first two as prior_directions
    assert "prior_directions" in ctx.lower() or "prior directions" in ctx.lower()
    # Both preceding slide_types should appear in the third clip's prior list
    ch1_03_idx = ctx.find("ch1_03")
    assert ch1_03_idx > 0
    slice_after = ctx[ch1_03_idx:]
    assert "banner_intro" in slice_after
    assert "photo_organism" in slice_after
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_direct_prepare_v2.py::test_prior_directions_included_in_per_clip_context -v`
Expected: FAIL — assertions do not hold against current output

- [ ] **Step 4: Implement prior_directions**

Open `src/docugen/direct.py`. Locate `prepare_direction_context` (or equivalent function the test imports). Inside the loop that builds per-clip context, before emitting each clip's block, compute a `prior_directions` list:

```python
def _prior_directions_summary(clips: list[dict], current_index: int) -> list[dict]:
    """Summarize direction decisions made in all preceding clips (flat list)."""
    priors = []
    for i in range(current_index):
        prev = clips[i]
        d = prev.get("direction") or {}
        priors.append({
            "clip_id": prev.get("clip_id"),
            "slide_type": d.get("slide_type"),
            "transition_in": d.get("transition_in"),
        })
    return priors
```

Integrate: inside the existing per-clip context builder, flatten all clips across chapters into a single ordered list so `current_index` is well-defined. Emit the `prior_directions` JSON block before the clip's own fields:

```python
# pseudo-integration — actual placement depends on existing structure
flat = []
for chapter in clips_data["chapters"]:
    for clip in chapter["clips"]:
        flat.append(clip)

for i, clip in enumerate(flat):
    priors = _prior_directions_summary(flat, i)
    # ...existing context building for clip...
    # insert near the top of the clip block:
    clip_block += f"\nprior_directions: {json.dumps(priors)}\n"
```

Also update the prompt preamble (the section that instructs the director on how to reason) to reference the new field:

```
When multiple slide_types would serve the content, prefer a slide_type and
transition_in that differ from those in prior_directions — the goal is
visual variety across adjacent chapters, not uniformity.
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_direct_prepare_v2.py -v`
Expected: all existing tests still PASS + new test PASS

- [ ] **Step 6: Commit**

```bash
git add src/docugen/direct.py tests/test_direct_prepare_v2.py
git commit -m "feat: direct_prepare adds prior_directions context for chapter variety"
```

---

### Task 9: Variety warning in `apply_direction`

**Files:**
- Modify: `src/docugen/direct.py`
- Modify: `tests/test_direct.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_direct.py`:

```python
def test_apply_direction_warns_on_three_same_slide_types(tmp_path, capsys):
    """Three consecutive clips with identical slide_type must emit a warning."""
    from docugen.direct import _variety_warnings

    directions = [
        {"clip_id": "ch1", "slide_type": "infographic"},
        {"clip_id": "ch2", "slide_type": "infographic"},
        {"clip_id": "ch3", "slide_type": "infographic"},
        {"clip_id": "ch4", "slide_type": "photo_organism"},
    ]
    warnings = _variety_warnings(directions)
    assert len(warnings) >= 1
    assert "infographic" in warnings[0]
    assert "ch1" in warnings[0] and "ch2" in warnings[0] and "ch3" in warnings[0]


def test_apply_direction_no_warning_when_broken_up():
    from docugen.direct import _variety_warnings

    directions = [
        {"clip_id": "ch1", "slide_type": "infographic"},
        {"clip_id": "ch2", "slide_type": "photo_organism"},
        {"clip_id": "ch3", "slide_type": "infographic"},
    ]
    assert _variety_warnings(directions) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_direct.py::test_apply_direction_warns_on_three_same_slide_types -v`
Expected: FAIL — `cannot import name '_variety_warnings'`

- [ ] **Step 3: Implement variety warning**

Add to `src/docugen/direct.py`:

```python
def _variety_warnings(directions: list[dict]) -> list[str]:
    """Warn when three consecutive clips share the same slide_type or transition_in."""
    warnings = []
    for i in range(len(directions) - 2):
        trio = directions[i:i+3]
        for field in ("slide_type", "transition_in"):
            values = [d.get(field) for d in trio]
            if values[0] is not None and values[0] == values[1] == values[2]:
                ids = ", ".join(d.get("clip_id", "?") for d in trio)
                warnings.append(
                    f"variety: three consecutive clips share {field}={values[0]!r}: {ids}"
                )
    return warnings
```

In `apply_direction` (or whatever function finalizes clips.json writes), after successful validation, collect warnings and print them (non-fatal):

```python
flat_directions = []
for chapter in clips_data["chapters"]:
    for clip in chapter["clips"]:
        if clip.get("direction"):
            flat_directions.append({"clip_id": clip["clip_id"], **clip["direction"]})

for w in _variety_warnings(flat_directions):
    print(f"[variety warning] {w}")
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_direct.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/docugen/direct.py tests/test_direct.py
git commit -m "feat: direct_apply warns when three consecutive clips share slide_type"
```

---

### Task 10: Move `generate_title` output to `build/title.mp4`

**Files:**
- Modify: `src/docugen/tools/title.py`
- Modify: `tests/test_title.py`

Today `generate_title` writes to `build/clips/intro_01.mp4` — that collides with the composite output directory (Task 11 gives composite full ownership of `build/clips/`). Move title output to `build/title.mp4` so it's a distinct artifact, and adjust the stitch auto-invocation (next task) to look there.

- [ ] **Step 1: Inspect current output path**

Run: `grep -n "intro_01.mp4\|build / \"clips\"" src/docugen/tools/title.py`
Note every place the title output path is constructed.

- [ ] **Step 2: Write the failing test**

Append to `tests/test_title.py` (or add a minimal focused test if the file is large):

```python
def test_generate_title_writes_to_build_title_mp4(tmp_path, monkeypatch):
    """Title output must land at build/title.mp4, not build/clips/intro_01.mp4."""
    from docugen.tools import title as title_mod

    proj = tmp_path
    (proj / "build").mkdir()
    (proj / "config.yaml").write_text("title: T\n")
    (proj / "build" / "plan.json").write_text(
        '{"title":"T","chapters":[{"id":"intro","title":"I","narration":"hi",'
        '"scene_type":"manim","images":[],"duration_estimate":2.0}]}'
    )

    def fake_run(cmd, *args, **kwargs):
        # Mirror manim's output: write an MP4 at whatever output dir is set
        class Result:
            returncode = 0
            stdout = b""
            stderr = b""
        for i, token in enumerate(cmd):
            if token == "--media_dir":
                media_dir = Path(cmd[i + 1])
                # Simulate manim's output structure — the renderer itself
                # already moves the file; we just need to produce some file
                # at the move source.
                (media_dir / "videos" / "_scene_title" / "1080p60").mkdir(
                    parents=True, exist_ok=True
                )
                (media_dir / "videos" / "_scene_title" / "1080p60" / "TitleScene.mp4").write_bytes(b"fake")
        return Result()

    monkeypatch.setattr("subprocess.run", fake_run)
    title_mod.generate_title(proj, duration=2.0)

    assert (proj / "build" / "title.mp4").exists()
    # Old path must no longer be produced
    assert not (proj / "build" / "clips" / "intro_01.mp4").exists()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_title.py::test_generate_title_writes_to_build_title_mp4 -v`
Expected: FAIL — current implementation still produces `build/clips/intro_01.mp4`.

- [ ] **Step 4: Change output path**

In `src/docugen/tools/title.py` within `generate_title`, replace the output path:

- Every `build / "clips" / "intro_01.mp4"` → `build / "title.mp4"`
- Every `build / "clips" / "_scene_title.py"` → `build / "_scene_title.py"` (script file lives at build/ root)
- Update the docstring step `5. Moves output to build/clips/intro_01.mp4` → `5. Moves output to build/title.mp4`

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_title.py -v`
Expected: all tests PASS. If any existing test asserted the old output path, update it to `build/title.mp4`.

- [ ] **Step 6: Commit**

```bash
git add src/docugen/tools/title.py tests/test_title.py
git commit -m "refactor: generate_title writes to build/title.mp4 (not build/clips/)"
```

---

### Task 11: Title auto-invocation in `stitch`

**Files:**
- Modify: `src/docugen/tools/stitch.py`
- Modify: `tests/test_stitch.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_stitch.py`:

```python
def test_stitch_auto_generates_title_when_missing(tmp_path, monkeypatch):
    """If build/title.mp4 is absent, stitch must invoke generate_title."""
    from docugen.tools import stitch as stitch_mod

    build = tmp_path / "build"
    build.mkdir()
    (build / "clips.json").write_text('{"chapters":[]}')
    (tmp_path / "config.yaml").write_text("title: T\n")

    called = {"n": 0}
    def fake_title(project_path, **kwargs):
        called["n"] += 1
        (tmp_path / "build" / "title.mp4").write_bytes(b"fake")
        return "ok"

    monkeypatch.setattr(stitch_mod, "generate_title", fake_title)
    # Prevent the rest of stitch from running — we only care about the title branch
    monkeypatch.setattr(stitch_mod, "_stitch_from_clips", lambda p: "stub")

    stitch_mod.stitch_all(tmp_path)
    assert called["n"] == 1


def test_stitch_skips_title_when_present(tmp_path, monkeypatch):
    from docugen.tools import stitch as stitch_mod

    build = tmp_path / "build"
    build.mkdir()
    (build / "clips.json").write_text('{"chapters":[]}')
    (build / "title.mp4").write_bytes(b"existing")
    (tmp_path / "config.yaml").write_text("title: T\n")

    called = {"n": 0}
    def fake_title(project_path, **kwargs):
        called["n"] += 1
        return "ok"

    monkeypatch.setattr(stitch_mod, "generate_title", fake_title)
    monkeypatch.setattr(stitch_mod, "_stitch_from_clips", lambda p: "stub")

    stitch_mod.stitch_all(tmp_path)
    assert called["n"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_stitch.py::test_stitch_auto_generates_title_when_missing -v`
Expected: FAIL — `generate_title` is not referenced in stitch.py

- [ ] **Step 3: Implement title auto-invocation**

Open `src/docugen/tools/stitch.py`. Add import at top:

```python
from docugen.tools.title import generate_title
```

Modify `stitch_all` to call `generate_title` before delegating to `_stitch_from_clips` / `_stitch_from_plan`:

Find:
```python
def stitch_all(project_path: str | Path) -> str:
    """Assemble clips, narration, and score into final video.

    Uses clips.json if available (per-clip assembly with pre-generated score).
    Falls back to plan.json (legacy, generates drone inline).
    """
    project_path = Path(project_path)
    build_dir = project_path / "build"

    if (build_dir / "clips.json").exists():
        return _stitch_from_clips(project_path)
    if (build_dir / "plan.json").exists():
        return _stitch_from_plan(project_path)
    raise FileNotFoundError("No clips.json or plan.json found.")
```

Replace with:
```python
def _ensure_title(project_path: Path) -> None:
    """Auto-generate build/title.mp4 if missing."""
    build_dir = project_path / "build"
    title_mp4 = build_dir / "title.mp4"
    if title_mp4.exists():
        return
    skip_marker = build_dir / "title.mp4.skip"
    if skip_marker.exists():
        return
    generate_title(project_path)


def stitch_all(project_path: str | Path) -> str:
    """Assemble clips, narration, and score into final video.

    Uses clips.json if available (per-clip assembly with pre-generated score).
    Falls back to plan.json (legacy, generates drone inline).

    Auto-invokes title tool if build/title.mp4 is missing. Touch
    build/title.mp4.skip to opt out.
    """
    project_path = Path(project_path)
    build_dir = project_path / "build"

    _ensure_title(project_path)

    if (build_dir / "clips.json").exists():
        return _stitch_from_clips(project_path)
    if (build_dir / "plan.json").exists():
        return _stitch_from_plan(project_path)
    raise FileNotFoundError("No clips.json or plan.json found.")
```

Also modify `_build_concat_file` and `_stitch_from_clips` to prepend title.mp4 to the concat list. Find in `_stitch_from_clips`:

```python
    ts_paths = []
    for chapter in clips_data["chapters"]:
        for clip in chapter["clips"]:
            src = clips_dir / f"{clip['clip_id']}.mp4"
```

Insert before the `for chapter` loop:
```python
    ts_paths = []
    title_mp4 = build_dir / "title.mp4"
    if title_mp4.exists():
        title_ts = ts_dir / "title.ts"
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(title_mp4),
             "-c", "copy", "-bsf:v", "h264_mp4toannexb",
             "-f", "mpegts", str(title_ts)],
            capture_output=True, text=True, check=True,
        )
        ts_paths.append(title_ts)
    for chapter in clips_data["chapters"]:
        for clip in chapter["clips"]:
            src = clips_dir / f"{clip['clip_id']}.mp4"
```

Remove the duplicate `ts_paths = []` line that was present before the loop originally.

Mirror in `_stitch_from_plan`: before its `_concatenate_clips` call, prepend title handling. Open `_concatenate_clips` and add at the start of the `for chapter in plan["chapters"]` loop body-building:

```python
    lines = []
    title_mp4 = build_dir / "title.mp4"
    if title_mp4.exists():
        lines.append(f"file '{title_mp4}'")
    for chapter in plan["chapters"]:
        clip = clips_dir / f"{chapter['id']}.mp4"
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_stitch.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/docugen/tools/stitch.py tests/test_stitch.py
git commit -m "feat: stitch auto-invokes title when build/title.mp4 is missing"
```

---

### Task 12: Route `render` output to `build/frames/`

**Files:**
- Modify: `src/docugen/tools/render.py`
- Modify: `tests/test_render.py`

Today `render_all` writes to `build/clips/<id>.mp4` — the same location where `composite` now produces the final clips. Renderer must write to `build/frames/<id>.mp4` instead, so composite's input/output paths don't collide.

- [ ] **Step 1: Scan render.py for the output path**

Run: `grep -n 'build / "clips"\|/ "clips" /' src/docugen/tools/render.py`
Note every line that constructs the per-clip output path.

- [ ] **Step 2: Write the failing test**

Append to `tests/test_render.py` (or create a focused test if the file is large):

```python
def test_render_output_path_is_frames_not_clips(tmp_path, monkeypatch):
    """render_all must write per-clip outputs to build/frames/, not build/clips/."""
    from docugen.tools import render as render_mod

    # Prevent actual Manim call — stub out the subprocess invocation that
    # executes Manim, and the script generator.
    captured_paths = []

    def fake_run(cmd, *args, **kwargs):
        # Mirror what Manim would produce: write a placeholder MP4 at the
        # path Manim is told to use.
        class Result:
            returncode = 0
            stdout = b""
            stderr = b""
        for token in cmd:
            if isinstance(token, str) and token.endswith(".mp4"):
                Path(token).parent.mkdir(parents=True, exist_ok=True)
                Path(token).write_bytes(b"stub")
                captured_paths.append(Path(token))
        return Result()

    monkeypatch.setattr("subprocess.run", fake_run)
    # Set up a minimal project
    proj = tmp_path
    (proj / "build").mkdir()
    (proj / "config.yaml").write_text("title: T\nvideo:\n  resolution: 1080p\n  fps: 30\n")
    (proj / "build" / "plan.json").write_text(
        '{"title":"T","chapters":[{"id":"intro","title":"I","narration":"hi",'
        '"scene_type":"manim","images":[],"duration_estimate":2.0}]}'
    )

    # Provide a narration WAV (render uses _get_wav_duration)
    import subprocess as _real_sp
    narr = proj / "build" / "narration"
    narr.mkdir()
    # Write a tiny real WAV so _get_wav_duration works
    _real_sp.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         "sine=frequency=200:duration=2.0", "-ar", "44100", "-ac", "1",
         str(narr / "intro.wav")],
        capture_output=True, check=True,
    )

    render_mod.render_all(proj)

    frames = [p for p in captured_paths if "frames" in p.parts]
    clips = [p for p in captured_paths if "clips" in p.parts]
    assert frames, f"expected frames/ output, got: {captured_paths}"
    assert not clips, f"render should not write to clips/: {clips}"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_render.py::test_render_output_path_is_frames_not_clips -v`
Expected: FAIL — output path still `clips/`

- [ ] **Step 4: Change output path in render.py**

Replace every `build / "clips"` with `build / "frames"` inside `render_chapter` and `render_all`. Keep the same per-clip filename convention (`<clip_id>.mp4`).

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_render.py -v`
Expected: the new test PASSes. Existing tests may need their expected paths updated — update any that asserted on `build/clips/<id>.mp4` from render output to `build/frames/<id>.mp4`.

- [ ] **Step 6: Commit**

```bash
git add src/docugen/tools/render.py tests/test_render.py
git commit -m "refactor: render writes to build/frames/ so composite owns build/clips/"
```

---

### Task 13: End-to-end integration check on perilux fixture

**Files:**
- Create: `tests/test_pipeline_integration.py`

This is a single slow integration test that runs the whole audio-first chain on a small synthetic fixture. Marked `@pytest.mark.slow` so it can be skipped in normal CI runs.

- [ ] **Step 1: Write the integration test**

Create `tests/test_pipeline_integration.py`:

```python
"""End-to-end integration test for audio-first pipeline.

Synthesizes a tiny project with pre-baked narration WAVs and Manim stand-ins,
then walks the post-narrate pipeline: base_clips -> composite. Verifies every
output clip duration equals clip_duration exactly.
"""
import json
import shutil
import subprocess
from pathlib import Path
import pytest

from docugen.tools.base_clips import generate_base_clips
from docugen.tools.composite import composite_all


pytestmark = pytest.mark.slow


def _make_video(path: Path, color: str, duration: float, w=1920, h=1080, fps=60):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"color=c={color}:s={w}x{h}:r={fps}",
         "-t", f"{duration}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
         str(path)],
        capture_output=True, text=True, check=True,
    )


def _make_wav(path: Path, duration: float):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"sine=frequency=200:duration={duration}",
         "-ar", "44100", "-ac", "1", str(path)],
        capture_output=True, text=True, check=True,
    )


def _probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def test_pipeline_produces_bounded_clips(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / "config.yaml").write_text(
        "title: Integration\nvideo:\n  resolution: 1080p\n  fps: 60\n"
    )

    clips = {"chapters": [{"id": "ch1", "clips": [
        {"clip_id": "ch1_01", "text": "one",   "timing": {"clip_duration": 2.0}},
        {"clip_id": "ch1_02", "text": "two",   "timing": {"clip_duration": 3.5}},
        {"clip_id": "ch1_03", "text": "three", "timing": {"clip_duration": 4.2}},
    ]}]}
    (proj / "build").mkdir()
    (proj / "build" / "clips.json").write_text(json.dumps(clips))

    # Narration WAVs: slightly shorter than clip_duration (normal case)
    for cid, cd in [("ch1_01", 1.8), ("ch1_02", 3.3), ("ch1_03", 4.0)]:
        _make_wav(proj / "build" / "narration" / f"{cid}.wav", cd)

    # Manim frames: varying overrun/underrun
    _make_video(proj / "build" / "frames" / "ch1_01.mp4", "red",   3.5)  # overrun
    _make_video(proj / "build" / "frames" / "ch1_02.mp4", "green", 2.0)  # underrun
    _make_video(proj / "build" / "frames" / "ch1_03.mp4", "blue",  4.2)  # exact

    generate_base_clips(proj)
    composite_all(proj)

    for cid, expected in [("ch1_01", 2.0), ("ch1_02", 3.5), ("ch1_03", 4.2)]:
        out = proj / "build" / "clips" / f"{cid}.mp4"
        assert out.exists()
        assert _probe_duration(out) == pytest.approx(expected, abs=0.06), (
            f"{cid}: expected {expected}s, got {_probe_duration(out)}s"
        )
```

- [ ] **Step 2: Run the integration test**

Run: `pytest tests/test_pipeline_integration.py -v`
Expected: PASS. Every output clip duration matches clip_duration ± 0.06s.

- [ ] **Step 3: Run the full test suite to confirm no regression**

Run: `pytest -v`
Expected: all tests PASS (including the existing test_render.py, test_stitch.py, test_plan.py, test_direct.py suites).

- [ ] **Step 4: Commit**

```bash
git add tests/test_pipeline_integration.py
git commit -m "test: end-to-end integration for audio-first pipeline bounds"
```

---

### Task 14: README + MCP instructions update

**Files:**
- Modify: `README.md`
- Modify: `src/docugen/server.py` (instructions string — already done in Task 6, verify)

- [ ] **Step 1: Update README pipeline table**

Open `README.md`. Find the pipeline overview section. Update the tool ordering to include the new stages and the gate:

Old:
```
init → plan_prepare → plan_apply → split → narrate → viz_extract →
direct_prepare → direct_apply → spot → render → score → stitch
```

New:
```
init → plan_prepare → plan_apply → split → narrate →
base_clips → storyboard_preview (review gate) → viz_extract →
direct_prepare → direct_apply → spot → render → composite →
score → stitch
```

Add a short blurb describing the audio-first contract and the storyboard gate:

```markdown
### Audio-first timeline

Narration is the authoritative timeline. `base_clips` emits a silent black
MP4 per clip at exactly `clip.timing.clip_duration`. Manim renders to
`build/frames/<id>.mp4`; `composite` overlays Manim onto the base, muxes
the narration WAV, and forces `-t clip_duration`. Drift is structurally
impossible.

### Storyboard preview (review gate)

Between narrate and direct, run `storyboard_preview` to produce
`build/storyboard.mp4`: each clip shows its index, content tag, and
subtitle over the base clip. Review timing end-to-end before spending
Manim compute.
```

- [ ] **Step 2: Verify MCP instructions string**

Run: `grep -n 'base_clips\|storyboard_preview\|composite' src/docugen/server.py`
Expected: matches in both the tool registrations (Tasks 2, 4, 6) and the `FastMCP` instructions string (Task 6).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: README covers audio-first pipeline + storyboard gate"
```

---

## Spec coverage check

| Spec section | Tasks |
|---|---|
| Pipeline shape changes | Tasks 2, 4, 6, 12, 14 |
| Audio-bound rendering (base_clips + composite + duration assertion) | Tasks 1, 5, 12, 13 |
| Storyboard preview gate | Tasks 3, 4 |
| Title output path + auto-wiring | Tasks 10, 11 |
| Chapter opener variety (prior_directions + warning) | Tasks 8, 9 |
| Short-emotive ban upstream | Task 7 |
| Error handling (ffmpeg failures, duration mismatch, validator errors) | Tasks 1, 5, 7 |
| Testing (unit + integration + regression) | Tasks 1–13 |
| Non-goals (no alpha Manim, no score/stitch rewrite beyond title) | honored throughout |

## Open questions resolved in this plan

1. **Short-emotive threshold** — set to `SHORT_WORD_CEIL = 1`, `HOT_EXAGGERATION_FLOOR = 0.3`, mirroring narrate.py's already-calibrated constants. User can tune both constants together later.
2. **Storyboard gate default** — opt-in. Run `storyboard_preview` explicitly; no marker file required.
3. **Manim overlay treatment** — solid black background, composited on base; black becomes transparent-adjacent because the base is already black.
4. **Title card duration** — handled by the `title` tool's default; no attempt to match opening narration length.
