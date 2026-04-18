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


def test_storyboard_overlay_renders_pixels(project):
    """Verify the overlay banner actually rendered — top strip is not pure black."""
    from PIL import Image
    import subprocess

    generate_storyboard_preview(project)
    storyboard = project / "build" / "storyboard.mp4"

    frame_path = project / "build" / "probe_frame.png"
    subprocess.run(
        ["ffmpeg", "-y", "-ss", "1.0", "-i", str(storyboard),
         "-vframes", "1", str(frame_path)],
        capture_output=True, text=True, check=True,
    )

    img = Image.open(frame_path).convert("RGB")
    w, h = img.size
    # Crop the top banner region where header text is drawn (y=18, fontsize≈36)
    banner = img.crop((60, 10, w - 60, 110))
    # Compute mean brightness; pure black banner = overlay failed to render
    pixels = list(banner.getdata())
    mean_brightness = sum(sum(p) for p in pixels) / (len(pixels) * 3)
    assert mean_brightness > 5, (
        f"banner appears black (mean brightness {mean_brightness:.2f}); "
        f"overlay likely did not render"
    )
