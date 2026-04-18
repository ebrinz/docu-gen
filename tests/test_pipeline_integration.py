"""End-to-end integration test for audio-first pipeline.

Synthesizes a tiny project with pre-baked narration WAVs and Manim stand-ins,
then walks the post-narrate pipeline: base_clips -> composite. Verifies every
output clip duration equals clip_duration exactly.
"""
import json
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
