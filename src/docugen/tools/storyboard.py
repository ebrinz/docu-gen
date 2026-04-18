"""Storyboard preview: burn clip id + content tag + subtitle onto base clips.

Run after base_clips. Produces build/storyboard.mp4 for end-to-end timing
review before any Manim rendering cost is paid.

Uses Pillow to render text overlay PNGs (avoids ffmpeg drawtext/freetype
dependency) then composites them via ffmpeg's overlay filter.
"""

import json
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


# ---- font resolution --------------------------------------------------------

_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Verdana Bold.ttf",
    "/System/Library/Fonts/Geneva.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ---- text helpers -----------------------------------------------------------

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
        parts.append(" \u00b7 ".join(assets))
    return " \u00b7 ".join(parts) if parts else "(no visual direction)"


def _wrap(text: str, width: int) -> str:
    return "\n".join(textwrap.wrap(text, width=width)) if text else ""


# ---- overlay PNG generation -------------------------------------------------

def _render_overlay_png(
    clip_index: int,
    clip: dict,
    width: int,
    height: int,
    out_path: Path,
) -> None:
    """Render a semi-transparent RGBA PNG with clip metadata text."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    header = f"CLIP {clip_index:02d} / {clip['clip_id']}"
    tag = _content_tag(clip)
    subtitle = _wrap(clip.get("text", ""), 55)

    font_header = _load_font(36)
    font_tag = _load_font(28)
    font_sub = _load_font(30)

    # semi-transparent top banner
    draw.rectangle([(0, 0), (width, 170)], fill=(0, 0, 0, 160))

    draw.text((60, 18), header, font=font_header, fill=(255, 255, 255, 255))
    draw.text((60, 70), tag, font=font_tag, fill=(245, 197, 24, 255))

    if subtitle:
        lines = subtitle.splitlines()
        line_h = 38
        total_h = len(lines) * line_h + 24
        y0 = height - total_h - 16
        draw.rectangle([(0, y0 - 8), (width, height)], fill=(0, 0, 0, 160))
        for i, line in enumerate(lines):
            draw.text((60, y0 + i * line_h), line, font=font_sub, fill=(255, 255, 255, 255))

    img.save(str(out_path), "PNG")


# ---- per-clip ffmpeg render -------------------------------------------------

def _probe_video_wh(path: Path) -> tuple[int, int]:
    """Return (width, height) of the first video stream."""
    out = subprocess.run(
        ["ffprobe", "-v", "error",
         "-select_streams", "v:0",
         "-show_entries", "stream=width,height",
         "-of", "csv=s=x:p=0",
         str(path)],
        capture_output=True, text=True, check=True,
    )
    w, h = out.stdout.strip().split("x")
    return int(w), int(h)


def _probe_duration(path: Path) -> float:
    """Return duration in seconds of a media file."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def _render_overlay_clip(
    base_path: Path,
    narration_path: Path | None,
    overlay_png: Path,
    out_path: Path,
) -> None:
    """Overlay PNG on video; video duration is authoritative (never truncated).

    For narration shorter than video: apad fills the gap.
    For silent clip: anullsrc padded to video length via -t.
    """
    video_duration = _probe_duration(base_path)

    if narration_path and narration_path.exists():
        # apad extends narration audio to match video duration; atrim ensures
        # narration longer than video doesn't extend it.
        cmd = [
            "ffmpeg", "-y",
            "-i", str(base_path),
            "-i", str(narration_path),
            "-i", str(overlay_png),
            "-filter_complex",
            "[1:a]apad,atrim=0:{dur}[a];[0:v][2:v]overlay=0:0[v]".format(
                dur=video_duration
            ),
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-t", f"{video_duration:.6f}",
            str(out_path),
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(base_path),
            "-f", "lavfi", "-i",
            f"anullsrc=channel_layout=stereo:sample_rate=44100:duration={video_duration:.6f}",
            "-i", str(overlay_png),
            "-filter_complex", "[0:v][2:v]overlay=0:0[v]",
            "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-t", f"{video_duration:.6f}",
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


# ---- public API -------------------------------------------------------------

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

            # Probe video dimensions for overlay PNG
            width, height = _probe_video_wh(base_path)

            # Render text overlay PNG via Pillow
            overlay_png = work_dir / f"{clip_id}_overlay.png"
            _render_overlay_png(index, clip, width, height, overlay_png)

            narr_path = narr_dir / f"{clip_id}.wav"
            overlay_mp4 = work_dir / f"{clip_id}.mp4"
            _render_overlay_clip(
                base_path,
                narr_path if narr_path.exists() else None,
                overlay_png,
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
