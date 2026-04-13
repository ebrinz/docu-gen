"""Title slide scene builder — Rajdhani font with 4 reveal styles."""

import json
import subprocess
from pathlib import Path

from docugen.config import load_config

# Default font directory resolved from module location
_FONT_DIR = str(Path(__file__).resolve().parent.parent.parent.parent / "assets" / "fonts")


def _escape(text: str) -> str:
    """Escape quotes for embedding in f-string generated scripts."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _particle_reveal(title: str, subtitle: str, duration: float,
                     colors: dict, font_dir: str) -> str:
    """300 dots drift, rush inward onto title path, flash, title appears."""
    title_esc = _escape(title)
    subtitle_esc = _escape(subtitle)
    bg = colors["bg"]
    gold = colors["accent_gold"]
    cyan = colors["accent_cyan"]

    return f'''from manim import *
import manimpango
import numpy as np
import random

manimpango.register_font("{font_dir}/Rajdhani-Bold.ttf")

config.background_color = "{bg}"

class Scene_title(Scene):
    def construct(self):
        # Title text (hidden initially, used for target points)
        title = Text("{title_esc}", font="Rajdhani Bold", color="{gold}").scale(1.4)
        subtitle = Text("{subtitle_esc}", font="Rajdhani SemiBold", color="{cyan}").scale(0.55)
        subtitle.next_to(title, DOWN, buff=0.6)

        # Sample target points from title path
        all_points = title.get_all_points()
        if len(all_points) > 300:
            indices = np.linspace(0, len(all_points) - 1, 300, dtype=int)
            targets = all_points[indices]
        else:
            targets = all_points

        # Create 300 drifting dots at random positions
        dots = VGroup()
        for i in range(300):
            x = random.uniform(-7, 7)
            y = random.uniform(-4, 4)
            dot = Dot(point=np.array([x, y, 0.0]), radius=0.03, color="{gold}")
            dot.set_opacity(0.6)
            dots.add(dot)

        self.add(dots)
        self.wait(0.5)

        # Drift phase
        self.play(
            *[dot.animate.shift(np.array([random.uniform(-0.5, 0.5),
                                          random.uniform(-0.5, 0.5), 0.0]))
              for dot in dots],
            run_time=1.5,
            rate_func=smooth,
        )

        # Rush inward to title path points
        anims = []
        for i, dot in enumerate(dots):
            idx = i % len(targets)
            anims.append(dot.animate.move_to(targets[idx]))
        self.play(*anims, run_time=1.5, rate_func=rush_into)

        # Flash
        flash = Rectangle(width=16, height=10, fill_color=WHITE,
                          fill_opacity=0.8, stroke_width=0)
        self.add(flash)
        self.play(flash.animate.set_opacity(0), run_time=0.3)
        self.remove(flash)

        # Dots fade, title appears
        self.play(FadeOut(dots), FadeIn(title), run_time=0.8)

        # Subtitle materializes via horizontal scanline
        scan_line = Line(LEFT * 8, RIGHT * 8, color="{cyan}", stroke_width=1)
        scan_line.move_to(subtitle.get_top())
        self.play(
            FadeIn(subtitle),
            scan_line.animate.move_to(subtitle.get_bottom()),
            run_time=1.2,
        )
        self.remove(scan_line)

        self.wait({max(duration - 6.5, 0.5):.1f})
        self.play(FadeOut(title), FadeOut(subtitle), run_time=1.5)
'''


def _glitch_reveal(title: str, subtitle: str, duration: float,
                   colors: dict, font_dir: str) -> str:
    """Title with RGB channel offset copies, jitter, then lock-in."""
    title_esc = _escape(title)
    subtitle_esc = _escape(subtitle)
    bg = colors["bg"]
    gold = colors["accent_gold"]
    cyan = colors["accent_cyan"]

    return f'''from manim import *
import manimpango

manimpango.register_font("{font_dir}/Rajdhani-Bold.ttf")

config.background_color = "{bg}"

class Scene_title(Scene):
    def construct(self):
        # Main title
        title = Text("{title_esc}", font="Rajdhani Bold", color="{gold}").scale(1.4)

        # RGB channel offset copies
        red_copy = Text("{title_esc}", font="Rajdhani Bold", color=RED).scale(1.4)
        red_copy.set_opacity(0.3)
        red_copy.shift(RIGHT * 0.06 + UP * 0.04)

        blue_copy = Text("{title_esc}", font="Rajdhani Bold", color=BLUE).scale(1.4)
        blue_copy.set_opacity(0.3)
        blue_copy.shift(LEFT * 0.06 + DOWN * 0.04)

        # Scanline overlay
        scanlines = VGroup()
        for y in range(-40, 40):
            line = Line(LEFT * 8, RIGHT * 8, stroke_width=0.5, color=WHITE)
            line.set_opacity(0.03)
            line.shift(UP * y * 0.1)
            scanlines.add(line)

        self.add(title, red_copy, blue_copy, scanlines)
        self.wait(0.3)

        # 6 rapid jitter frames
        import random
        for _ in range(6):
            jx = random.uniform(-0.08, 0.08)
            jy = random.uniform(-0.04, 0.04)
            self.play(
                red_copy.animate.shift(RIGHT * jx + UP * jy),
                blue_copy.animate.shift(LEFT * jx + DOWN * jy),
                run_time=0.12,
                rate_func=linear,
            )

        # Lock in — offsets converge to zero
        self.play(
            red_copy.animate.move_to(title.get_center()),
            blue_copy.animate.move_to(title.get_center()),
            red_copy.animate.set_opacity(0),
            blue_copy.animate.set_opacity(0),
            run_time=0.5,
        )
        self.remove(red_copy, blue_copy)

        # Subtitle types in letter by letter
        subtitle = Text("{subtitle_esc}", font="Rajdhani SemiBold", color="{cyan}").scale(0.55)
        subtitle.next_to(title, DOWN, buff=0.6)
        self.play(AddTextLetterByLetter(subtitle), run_time=1.5)

        self.wait({max(duration - 4.5, 0.5):.1f})
        self.play(FadeOut(title), FadeOut(subtitle), FadeOut(scanlines), run_time=1.0)
'''


def _trace_reveal(title: str, subtitle: str, duration: float,
                  colors: dict, font_dir: str) -> str:
    """DrawBorderThenFill with gold-to-cyan color sweep."""
    title_esc = _escape(title)
    subtitle_esc = _escape(subtitle)
    bg = colors["bg"]
    gold = colors["accent_gold"]
    cyan = colors["accent_cyan"]

    return f'''from manim import *
import manimpango

manimpango.register_font("{font_dir}/Rajdhani-Bold.ttf")

config.background_color = "{bg}"

class Scene_title(Scene):
    def construct(self):
        title = Text("{title_esc}", font="Rajdhani Bold", color="{gold}").scale(1.4)
        subtitle = Text("{subtitle_esc}", font="Rajdhani SemiBold", color="{cyan}").scale(0.55)
        subtitle.next_to(title, DOWN, buff=0.6)

        # Draw border then fill
        self.play(DrawBorderThenFill(title), run_time=2.5)

        # Gold-to-cyan color sweep via ValueTracker
        tracker = ValueTracker(0)

        def update_color(mob):
            t = tracker.get_value()
            if t <= 0.5:
                alpha = t * 2
                mob.set_color(interpolate_color(
                    ManimColor("{gold}"), ManimColor("{cyan}"), alpha))
            else:
                alpha = (t - 0.5) * 2
                mob.set_color(interpolate_color(
                    ManimColor("{cyan}"), ManimColor("{gold}"), alpha))

        title.add_updater(update_color)
        self.play(tracker.animate.set_value(1.0), run_time=2.0)
        title.remove_updater(update_color)
        title.set_color("{gold}")

        # Subtitle fades in
        self.play(FadeIn(subtitle, shift=UP * 0.2), run_time=1.0)

        self.wait({max(duration - 6.5, 0.5):.1f})
        self.play(FadeOut(title), FadeOut(subtitle), run_time=1.0)
'''


def _typewriter_reveal(title: str, subtitle: str, duration: float,
                       colors: dict, font_dir: str) -> str:
    """Cursor blinks, then title types in letter by letter."""
    title_esc = _escape(title)
    subtitle_esc = _escape(subtitle)
    bg = colors["bg"]
    gold = colors["accent_gold"]
    cyan = colors["accent_cyan"]

    return f'''from manim import *
import manimpango

manimpango.register_font("{font_dir}/Rajdhani-Bold.ttf")

config.background_color = "{bg}"

class Scene_title(Scene):
    def construct(self):
        # Blinking cursor
        cursor = Rectangle(width=0.08, height=0.8, fill_color="{gold}",
                           fill_opacity=1.0, stroke_width=0)
        cursor.move_to(LEFT * 3)

        # Blink twice
        self.add(cursor)
        for _ in range(2):
            self.play(cursor.animate.set_opacity(0), run_time=0.25)
            self.play(cursor.animate.set_opacity(1), run_time=0.25)

        # Type in title
        title = Text("{title_esc}", font="Rajdhani Bold", color="{gold}").scale(1.4)
        title.move_to(ORIGIN)
        cursor.move_to(title.get_left() + LEFT * 0.1)

        self.play(
            AddTextLetterByLetter(title),
            cursor.animate.move_to(title.get_right() + RIGHT * 0.1),
            run_time=2.0,
        )

        # Cursor fades
        self.play(FadeOut(cursor), run_time=0.3)

        # Subtitle fades in
        subtitle = Text("{subtitle_esc}", font="Rajdhani SemiBold", color="{cyan}").scale(0.55)
        subtitle.next_to(title, DOWN, buff=0.6)
        self.play(FadeIn(subtitle, shift=UP * 0.2), run_time=1.0)

        self.wait({max(duration - 5.5, 0.5):.1f})
        self.play(FadeOut(title), FadeOut(subtitle), run_time=1.0)
'''


# Style dispatch
_STYLES = {
    "particle": _particle_reveal,
    "glitch": _glitch_reveal,
    "trace": _trace_reveal,
    "typewriter": _typewriter_reveal,
}


def build_title_script(title: str, subtitle: str, reveal_style: str = "particle",
                       duration: float = 8.0, colors: dict | None = None,
                       font_dir: str | None = None) -> str:
    """Generate a complete Manim Python script for a title slide.

    Args:
        title: Main title text.
        subtitle: Subtitle text.
        reveal_style: One of particle, glitch, trace, typewriter.
        duration: Total scene duration in seconds.
        colors: Dict with bg, accent_gold, accent_cyan, text keys.
        font_dir: Path to directory containing Rajdhani font files.

    Returns:
        A complete standalone Manim Python script as a string.
    """
    if colors is None:
        colors = {
            "bg": "#0a0e27",
            "accent_gold": "#f59e0b",
            "accent_cyan": "#22d3ee",
            "text": "#e2e8f0",
        }
    if font_dir is None:
        font_dir = _FONT_DIR

    builder = _STYLES.get(reveal_style, _particle_reveal)
    return builder(title, subtitle, duration, colors, font_dir)


def generate_title(project_path: str | Path, reveal_style: str = "particle",
                   title: str | None = None, subtitle: str | None = None,
                   duration: float = 8.0) -> str:
    """Render a title slide to MP4.

    1. Reads config and production plan for defaults
    2. Calls build_title_script to generate the Manim script
    3. Writes script to build/clips/_scene_title.py
    4. Runs manim subprocess to render
    5. Moves output to build/clips/intro_01.mp4
    6. Cleans up script file

    Returns:
        Path to the rendered intro_01.mp4.
    """
    project_path = Path(project_path)
    config = load_config(project_path)

    # Read defaults from production plan
    plan_path = project_path / "build" / "plan.json"
    if plan_path.exists():
        plan = json.loads(plan_path.read_text())
        meta = plan.get("meta", plan)
        if title is None:
            title = meta.get("title", "Untitled")
        if subtitle is None:
            subtitle = meta.get("subtitle", "")
        palette = meta.get("color_palette", {})
    else:
        if title is None:
            title = "Untitled"
        if subtitle is None:
            subtitle = ""
        palette = {}

    colors = {
        "bg": palette.get("bg", "#0a0e27"),
        "accent_gold": palette.get("accent_gold", "#f59e0b"),
        "accent_cyan": palette.get("accent_cyan", "#22d3ee"),
        "text": palette.get("text", "#e2e8f0"),
    }

    font_dir = _FONT_DIR
    script = build_title_script(title, subtitle, reveal_style, duration, colors, font_dir)

    clips_dir = project_path / "build" / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    media_dir = clips_dir / "media"

    script_path = clips_dir / "_scene_title.py"
    script_path.write_text(script)

    fps = config["video"]["fps"]
    quality = "-qh" if fps >= 60 else "-qm"

    result = subprocess.run(
        ["manim", quality, str(script_path.resolve()), "Scene_title",
         "--media_dir", str(media_dir.resolve()), "--format", "mp4"],
        capture_output=True, text=True,
    )

    if result.returncode != 0:
        script_path.unlink(missing_ok=True)
        raise RuntimeError(f"Manim render failed for title:\n{result.stderr[-500:]}")

    output_files = list(media_dir.rglob("Scene_title.mp4"))
    if not output_files:
        script_path.unlink(missing_ok=True)
        raise FileNotFoundError("Manim output not found for Scene_title")

    final_path = clips_dir / "intro_01.mp4"
    output_files[0].rename(final_path)
    script_path.unlink(missing_ok=True)

    return str(final_path)
