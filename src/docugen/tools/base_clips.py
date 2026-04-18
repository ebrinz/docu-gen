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
