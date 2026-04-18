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
