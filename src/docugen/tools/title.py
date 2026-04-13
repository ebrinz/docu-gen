"""Title slide scene builder — Audiowide font with 4 reveal styles + biopunk theming."""

import json
import subprocess
from pathlib import Path

from docugen.config import load_config

# Default font directory resolved from module location
_FONT_DIR = str(Path(__file__).resolve().parent.parent.parent.parent / "assets" / "fonts")

# Biopunk theme elements injected into every title scene
_BIOPUNK_HEADER = '''
# ── Biopunk theme elements ──────────────────────────────────────
def hex_grid(scene, color, dim_color, rows=6, cols=10):
    """Draw a subtle hex grid background."""
    grid = VGroup()
    for r in range(rows):
        for c in range(cols):
            x = (c - cols / 2) * 1.5 + (0.75 if r % 2 else 0)
            y = (r - rows / 2) * 1.3
            hexagon = RegularPolygon(n=6, radius=0.7, color=dim_color,
                                     stroke_width=0.5, stroke_opacity=0.15)
            hexagon.move_to([x, y, 0])
            grid.add(hexagon)
    scene.add(grid)
    return grid

def imperial_border(scene, color):
    """Draw corner bracket HUD frame."""
    corners = VGroup()
    for x_sign, y_sign in [(-1,1), (1,1), (1,-1), (-1,-1)]:
        cx, cy = x_sign * 6.8, y_sign * 3.7
        h = Line([cx, cy, 0], [cx - x_sign * 1.0, cy, 0],
                 color=color, stroke_width=1.5, stroke_opacity=0.6)
        v = Line([cx, cy, 0], [cx, cy - y_sign * 1.0, 0],
                 color=color, stroke_width=1.5, stroke_opacity=0.6)
        corners.add(h, v)
    scene.play(Create(corners, lag_ratio=0.05), run_time=0.8)
    return corners

def floating_particles(scene, n=80, color="#b8ffc4"):
    """Create softly glowing background particles."""
    import random as _rng
    particles = VGroup()
    for _ in range(n):
        x = _rng.uniform(-7.5, 7.5)
        y = _rng.uniform(-4.5, 4.5)
        r = _rng.uniform(0.01, 0.04)
        opacity = _rng.uniform(0.05, 0.2)
        dot = Dot(point=[x, y, 0], radius=r, color=color)
        dot.set_opacity(opacity)
        particles.add(dot)
    scene.add(particles)
    return particles
'''


def _escape(text: str) -> str:
    """Escape quotes for embedding in f-string generated scripts."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _particle_reveal(title: str, subtitle: str, duration: float,
                     colors: dict, font_dir: str) -> str:
    """Particles converge into title letterforms over biopunk background."""
    title_esc = _escape(title)
    subtitle_esc = _escape(subtitle)
    bg = colors["bg"]
    gold = colors["accent_gold"]
    cyan = colors["accent_cyan"]
    glow = colors.get("glow", "#b8ffc4")
    grid_color = colors.get("grid", "#1a1a2e")

    return f'''from manim import *
import manimpango
import numpy as np
import random

manimpango.register_font("{font_dir}/Audiowide-Regular.ttf")

config.background_color = "{bg}"
{_BIOPUNK_HEADER}

class Scene_title(Scene):
    def construct(self):
        # Biopunk theme layers
        grid = hex_grid(self, "{gold}", "{grid_color}")
        particles = floating_particles(self, n=80, color="{glow}")
        border = imperial_border(self, "{gold}")

        # Title text — scale to fit screen width
        title = Text("{title_esc}", font="Audiowide", color="{gold}")
        # Auto-scale: if wider than 12 units, shrink to fit
        if title.width > 12:
            title.scale(11.5 / title.width)
        else:
            title.scale(min(1.2, 12 / title.width))
        title.shift(UP * 0.5)

        subtitle = Text("{subtitle_esc}", font="Audiowide", color="{cyan}")
        if subtitle.width > 12:
            subtitle.scale(11 / subtitle.width)
        else:
            subtitle.scale(min(0.45, 11 / subtitle.width))
        subtitle.next_to(title, DOWN, buff=0.5)

        # Sample target points from title path
        all_points = title.get_all_points()
        n_dots = 300
        if len(all_points) > n_dots:
            indices = np.linspace(0, len(all_points) - 1, n_dots, dtype=int)
            targets = all_points[indices]
        else:
            targets = all_points
            n_dots = len(targets)

        # Create converging dots at random positions
        dots = VGroup()
        for i in range(n_dots):
            x = random.uniform(-8, 8)
            y = random.uniform(-5, 5)
            dot = Dot(point=np.array([x, y, 0.0]), radius=0.025, color="{gold}")
            dot.set_opacity(0.5)
            dots.add(dot)

        self.add(dots)
        self.wait(0.3)

        # Gentle drift
        self.play(
            *[dot.animate.shift(np.array([random.uniform(-0.4, 0.4),
                                          random.uniform(-0.3, 0.3), 0.0]))
              for dot in dots],
            run_time=1.5, rate_func=smooth,
        )

        # Rush inward to title path points
        anims = []
        for i, dot in enumerate(dots):
            idx = i % len(targets)
            anims.append(dot.animate.move_to(targets[idx]).set_opacity(0.9))
        self.play(*anims, run_time=2.0, rate_func=rush_into)

        # Brief gold flash
        flash = Rectangle(width=16, height=10, fill_color="{gold}",
                          fill_opacity=0.25, stroke_width=0)
        self.add(flash)
        self.play(flash.animate.set_opacity(0), run_time=0.25)
        self.remove(flash)

        # Dots fade, title appears
        self.play(FadeOut(dots), FadeIn(title), run_time=0.6)

        # Subtitle via horizontal scanline
        scan = Line(LEFT * 8, RIGHT * 8, color="{cyan}", stroke_width=1, stroke_opacity=0.6)
        scan.move_to(subtitle.get_top() + UP * 0.1)
        self.play(
            FadeIn(subtitle),
            scan.animate.move_to(subtitle.get_bottom() + DOWN * 0.1),
            run_time=1.0,
        )
        self.remove(scan)

        # Gentle particle drift during hold
        hold = max({duration} - 7.0, 1.0)
        drift_anims = []
        for p in particles:
            dx = random.uniform(-0.3, 0.3)
            dy = random.uniform(-0.2, 0.2)
            drift_anims.append(p.animate.shift([dx, dy, 0]))
        self.play(*drift_anims, run_time=hold, rate_func=linear)

        self.play(FadeOut(title), FadeOut(subtitle), run_time=1.5)
'''


def _glitch_reveal(title: str, subtitle: str, duration: float,
                   colors: dict, font_dir: str) -> str:
    """Title with RGB channel offset, scanline jitter, then lock-in."""
    title_esc = _escape(title)
    subtitle_esc = _escape(subtitle)
    bg = colors["bg"]
    gold = colors["accent_gold"]
    cyan = colors["accent_cyan"]
    glow = colors.get("glow", "#b8ffc4")
    grid_color = colors.get("grid", "#1a1a2e")

    return f'''from manim import *
import manimpango
import random

manimpango.register_font("{font_dir}/Audiowide-Regular.ttf")

config.background_color = "{bg}"
{_BIOPUNK_HEADER}

class Scene_title(Scene):
    def construct(self):
        # Biopunk theme layers
        grid = hex_grid(self, "{gold}", "{grid_color}")
        particles = floating_particles(self, n=60, color="{glow}")
        border = imperial_border(self, "{gold}")

        # Title — auto-scale to fit
        title = Text("{title_esc}", font="Audiowide", color="{gold}")
        if title.width > 12:
            title.scale(11.5 / title.width)
        else:
            title.scale(min(1.2, 12 / title.width))
        title.shift(UP * 0.5)

        # RGB offset copies
        red_copy = title.copy().set_color(RED).set_opacity(0.3)
        red_copy.shift(RIGHT * 0.06 + UP * 0.04)
        blue_copy = title.copy().set_color(BLUE).set_opacity(0.3)
        blue_copy.shift(LEFT * 0.06 + DOWN * 0.04)

        # Scanline overlay
        scanlines = VGroup()
        for y_i in range(-40, 40):
            line = Line(LEFT * 8, RIGHT * 8, stroke_width=0.5, color=WHITE)
            line.set_opacity(0.03)
            line.shift(UP * y_i * 0.1)
            scanlines.add(line)

        self.add(title, red_copy, blue_copy, scanlines)
        self.wait(0.2)

        # 6 rapid jitter frames
        for _ in range(6):
            jx = random.uniform(-0.08, 0.08)
            jy = random.uniform(-0.04, 0.04)
            red_copy.shift(RIGHT * jx + UP * jy)
            blue_copy.shift(LEFT * jx + DOWN * jy)
            self.wait(0.08)

        # Lock in
        self.play(
            red_copy.animate.move_to(title.get_center()).set_opacity(0),
            blue_copy.animate.move_to(title.get_center()).set_opacity(0),
            scanlines.animate.set_opacity(0.01),
            run_time=0.8, rate_func=rush_from,
        )
        self.remove(red_copy, blue_copy)

        # Subtitle types in
        subtitle = Text("{subtitle_esc}", font="Audiowide", color="{cyan}")
        if subtitle.width > 12:
            subtitle.scale(11 / subtitle.width)
        else:
            subtitle.scale(min(0.45, 11 / subtitle.width))
        subtitle.next_to(title, DOWN, buff=0.5)
        self.play(AddTextLetterByLetter(subtitle), run_time=1.5)

        self.wait({max(duration - 4.5, 0.5):.1f})
        self.play(FadeOut(title), FadeOut(subtitle), FadeOut(scanlines), run_time=1.0)
'''


def _trace_reveal(title: str, subtitle: str, duration: float,
                  colors: dict, font_dir: str) -> str:
    """DrawBorderThenFill with gold-to-cyan color sweep over biopunk bg."""
    title_esc = _escape(title)
    subtitle_esc = _escape(subtitle)
    bg = colors["bg"]
    gold = colors["accent_gold"]
    cyan = colors["accent_cyan"]
    glow = colors.get("glow", "#b8ffc4")
    grid_color = colors.get("grid", "#1a1a2e")

    return f'''from manim import *
import manimpango

manimpango.register_font("{font_dir}/Audiowide-Regular.ttf")

config.background_color = "{bg}"
{_BIOPUNK_HEADER}

class Scene_title(Scene):
    def construct(self):
        # Biopunk theme layers
        grid = hex_grid(self, "{gold}", "{grid_color}")
        particles = floating_particles(self, n=60, color="{glow}")
        border = imperial_border(self, "{gold}")

        title = Text("{title_esc}", font="Audiowide", color="{gold}")
        if title.width > 12:
            title.scale(11.5 / title.width)
        else:
            title.scale(min(1.2, 12 / title.width))
        title.shift(UP * 0.5)

        subtitle = Text("{subtitle_esc}", font="Audiowide", color="{cyan}")
        if subtitle.width > 12:
            subtitle.scale(11 / subtitle.width)
        else:
            subtitle.scale(min(0.45, 11 / subtitle.width))
        subtitle.next_to(title, DOWN, buff=0.5)

        # Draw border then fill
        self.play(DrawBorderThenFill(title), run_time=2.5)

        # Gold-to-cyan color sweep
        tracker = ValueTracker(0)
        def update_color(mob):
            t = tracker.get_value()
            if t <= 0.5:
                mob.set_color(interpolate_color(
                    ManimColor("{gold}"), ManimColor("{cyan}"), t * 2))
            else:
                mob.set_color(interpolate_color(
                    ManimColor("{cyan}"), ManimColor("{gold}"), (t - 0.5) * 2))

        title.add_updater(update_color)
        self.play(tracker.animate.set_value(1.0), run_time=2.0)
        title.remove_updater(update_color)
        title.set_color("{gold}")

        # Subtitle fades in
        self.play(FadeIn(subtitle, shift=UP * 0.2), run_time=1.0)

        self.wait({max(duration - 7.0, 0.5):.1f})
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
    glow = colors.get("glow", "#b8ffc4")
    grid_color = colors.get("grid", "#1a1a2e")

    return f'''from manim import *
import manimpango

manimpango.register_font("{font_dir}/Audiowide-Regular.ttf")

config.background_color = "{bg}"
{_BIOPUNK_HEADER}

class Scene_title(Scene):
    def construct(self):
        # Biopunk theme layers
        grid = hex_grid(self, "{gold}", "{grid_color}")
        particles = floating_particles(self, n=60, color="{glow}")
        border = imperial_border(self, "{gold}")

        # Title — auto-scale to fit
        title = Text("{title_esc}", font="Audiowide", color="{gold}")
        if title.width > 12:
            title.scale(11.5 / title.width)
        else:
            title.scale(min(1.2, 12 / title.width))
        title.shift(UP * 0.5)

        # Blinking cursor
        cursor = Rectangle(width=0.06, height=title.height * 0.9,
                           fill_color="{gold}", fill_opacity=1.0, stroke_width=0)
        cursor.move_to(title.get_left() + LEFT * 0.15)

        self.add(cursor)
        for _ in range(2):
            self.play(cursor.animate.set_opacity(0), run_time=0.25)
            self.play(cursor.animate.set_opacity(1), run_time=0.25)

        # Type title
        self.play(
            AddTextLetterByLetter(title),
            cursor.animate.move_to(title.get_right() + RIGHT * 0.15),
            run_time=2.0,
        )
        self.play(FadeOut(cursor), run_time=0.3)

        # Subtitle fades in
        subtitle = Text("{subtitle_esc}", font="Audiowide", color="{cyan}")
        if subtitle.width > 12:
            subtitle.scale(11 / subtitle.width)
        else:
            subtitle.scale(min(0.45, 11 / subtitle.width))
        subtitle.next_to(title, DOWN, buff=0.5)
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
        colors: Dict with bg, accent_gold, accent_cyan, glow, grid keys.
        font_dir: Path to directory containing Audiowide font file.

    Returns:
        A complete standalone Manim Python script as a string.
    """
    if colors is None:
        colors = {
            "bg": "#050510",
            "accent_gold": "#f59e0b",
            "accent_cyan": "#22d3ee",
            "glow": "#b8ffc4",
            "grid": "#1a1a2e",
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
        "bg": palette.get("bg", "#050510"),
        "accent_gold": palette.get("accent_gold", "#f59e0b"),
        "accent_cyan": palette.get("accent_cyan", "#22d3ee"),
        "glow": "#b8ffc4",
        "grid": "#1a1a2e",
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
    if final_path.exists():
        final_path.unlink()
    output_files[0].rename(final_path)
    script_path.unlink(missing_ok=True)

    return str(final_path)
