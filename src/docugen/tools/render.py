"""Render tool: generate Manim scenes per chapter and render to MP4."""

import json
import subprocess
from pathlib import Path

from scipy.io import wavfile

from docugen.config import load_config

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
    """Generate a Manim Python script for a single chapter scene."""
    cid = chapter["id"]
    title = chapter["title"]
    scene_type = chapter["scene_type"]
    images = chapter.get("images", [])
    class_name = f"Scene_{cid}"

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


def _intro_script(class_name, doc_title, subtitle, duration):
    return f'''from manim import *

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


def _outro_script(class_name, doc_title, title, duration):
    return f'''from manim import *

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


def _chapter_card_script(class_name, title, duration):
    return f'''from manim import *

config.background_color = "{BG}"

class {class_name}(Scene):
    def construct(self):
        title = Text("{title}", color="{WHITE}").scale(0.9)
        self.play(FadeIn(title, shift=RIGHT * 0.3), run_time=1.5)
        self.wait({max(duration - 3.0, 1.0):.1f})
        self.play(FadeOut(title), run_time=1.5)
'''


def _mixed_script(class_name, title, duration, images, images_dir):
    """Scene with chapter card + images with Ken Burns motion."""
    images_dir_str = str(images_dir).replace("\\", "\\\\")
    image_items = ", ".join(f'"{img}"' for img in images)
    time_per_image = max((duration - 4.0) / max(len(images), 1), 2.0)

    return f'''from manim import *
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
            self.play(
                img.animate.scale(1.08),
                run_time={time_per_image:.1f},
                rate_func=linear,
            )
            self.play(FadeOut(img), run_time=0.8)
'''


def render_chapter(project_path: Path, chapter: dict, doc_title: str,
                   duration: float) -> str:
    """Render a single chapter to MP4 using Manim."""
    project_path = Path(project_path)
    config = load_config(project_path)
    cid = chapter["id"]
    images_dir = project_path / "images"
    clips_dir = project_path / "build" / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    script = build_manim_script(chapter, doc_title, duration, images_dir)
    class_name = f"Scene_{cid}"

    script_path = clips_dir / f"_scene_{cid}.py"
    script_path.write_text(script)

    fps = config["video"]["fps"]
    quality = "-qh" if fps >= 60 else "-qm"

    cmd = [
        "manim", quality,
        str(script_path), class_name,
        "--media_dir", str(clips_dir / "media"),
        "--format", "mp4",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(clips_dir))
    if result.returncode != 0:
        raise RuntimeError(f"Manim render failed for {cid}:\n{result.stderr}")

    output_files = list((clips_dir / "media").rglob(f"{class_name}.mp4"))
    if not output_files:
        raise FileNotFoundError(f"Manim output not found for {class_name}")

    final_path = clips_dir / f"{cid}.mp4"
    output_files[0].rename(final_path)
    script_path.unlink(missing_ok=True)

    return str(final_path)


def render_all(project_path: str | Path) -> str:
    """Render all chapters in plan.json to individual MP4 clips."""
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
        wav_path = narration_dir / f"{cid}.wav"
        if wav_path.exists():
            duration = _get_wav_duration(wav_path)
        else:
            duration = chapter.get("duration_estimate", 30.0)

        clip_path = render_chapter(project_path, chapter, plan["title"], duration)
        results.append(f"{cid}.mp4 ({duration:.1f}s)")

    return "Rendered clips:\n" + "\n".join(results)
