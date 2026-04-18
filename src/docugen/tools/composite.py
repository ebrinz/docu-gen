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
