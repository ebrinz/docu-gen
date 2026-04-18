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

    def fake_probe(path):
        return 999.0
    monkeypatch.setattr(cmod, "_probe_duration", fake_probe)

    with pytest.raises(RuntimeError, match="duration mismatch"):
        composite_all(project)


def test_composite_includes_narration_audio_when_wav_present(project):
    """When a narration WAV exists, the output must carry its audio stream."""
    composite_all(project)

    out = project / "build" / "clips" / "intro_01.mp4"
    # ffprobe the audio stream to confirm it's present and non-empty
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_type,duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(out)],
        capture_output=True, text=True, check=True,
    )
    lines = result.stdout.strip().split("\n")
    assert "audio" in lines, f"expected audio stream, got: {result.stdout}"


def test_composite_registered_as_mcp_tool():
    from docugen import server
    tool_names = [t.name for t in server.mcp._tool_manager.list_tools()]
    assert "composite" in tool_names
