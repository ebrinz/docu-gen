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

    if scene_type == "banner_intro":
        return _banner_intro_script(class_name, title_esc, duration, images, images_dir)
    elif scene_type == "banner_outro":
        return _banner_outro_script(class_name, doc_title_esc, title_esc, duration, images, images_dir)
    elif scene_type == "infographic":
        diagram_type = chapter.get("diagram_type", "default")
        return _infographic_script(class_name, title_esc, duration, diagram_type, images_dir)
    elif cid == "intro":
        return _intro_script(class_name, doc_title_esc, title_esc, duration)
    elif cid == "outro":
        return _outro_script(class_name, doc_title_esc, title_esc, duration)
    elif scene_type == "mixed" and images:
        return _mixed_script(class_name, title_esc, duration, images, images_dir)
    else:
        return _chapter_card_script(class_name, title_esc, duration)


def _intro_script(class_name, doc_title, subtitle, duration):
    # Split long titles into stacked lines at colon, dash, or midpoint
    if len(doc_title) > 20:
        for sep in [":", " — ", " - "]:
            if sep in doc_title:
                parts = doc_title.split(sep, 1)
                line1 = parts[0].strip()
                line2 = parts[1].strip()
                break
        else:
            words = doc_title.split()
            mid = len(words) // 2
            line1 = " ".join(words[:mid])
            line2 = " ".join(words[mid:])
    else:
        line1 = doc_title
        line2 = None

    if line2:
        line1_esc = line1.replace('"', '\\"')
        line2_esc = line2.replace('"', '\\"')
        return f'''from manim import *

config.background_color = "{BG}"

class {class_name}(Scene):
    def construct(self):
        line1 = Text("{line1_esc}", color="{GOLD}").scale(1.4)
        line2 = Text("{line2_esc}", color="{GOLD}").scale(0.7)
        line2.next_to(line1, DOWN, buff=0.3)
        title_group = VGroup(line1, line2).move_to(ORIGIN)
        subtitle = Text("{subtitle}", color="{TEAL}").scale(0.6)
        subtitle.next_to(title_group, DOWN, buff=0.6)

        self.play(FadeIn(line1, shift=UP * 0.3), run_time=2.0)
        self.play(FadeIn(line2, shift=UP * 0.2), run_time=1.0)
        self.play(FadeIn(subtitle, shift=UP * 0.2), run_time=1.5)
        self.wait({max(duration - 6.0, 1.0):.1f})
        self.play(FadeOut(title_group), FadeOut(subtitle), run_time=1.5)
'''
    else:
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


def _banner_intro_script(class_name, subtitle, duration, images, images_dir):
    """Intro scene using banner image as title card."""
    images_dir_str = str(images_dir).replace("\\", "\\\\")
    banner = images[0] if images else "banner.png"

    return f'''from manim import *
from pathlib import Path

config.background_color = "{BG}"

class {class_name}(Scene):
    def construct(self):
        img_path = Path("{images_dir_str}") / "{banner}"
        banner = ImageMobject(str(img_path))
        banner.height = 7.0
        banner.width = 12.0

        subtitle = Text("{subtitle}", color="{TEAL}").scale(0.5)
        subtitle.to_edge(DOWN, buff=0.5)

        self.play(FadeIn(banner, run_time=2.0))
        self.play(
            banner.animate.scale(1.06),
            run_time={max(duration - 5.0, 3.0):.1f},
            rate_func=linear,
        )
        self.play(FadeIn(subtitle, shift=UP * 0.2), run_time=1.5)
        self.wait(0.5)
        self.play(FadeOut(banner), FadeOut(subtitle), run_time=1.0)
'''


def _banner_outro_script(class_name, doc_title, title, duration, images, images_dir):
    """Outro scene with closing tagline on dark background."""
    title_esc = title.replace('"', '\\"')

    return f'''from manim import *

config.background_color = "{BG}"

class {class_name}(Scene):
    def construct(self):
        tagline = Text("{title_esc}", color="{GOLD}").scale(0.8)
        tagline.move_to(ORIGIN)

        self.play(FadeIn(tagline, shift=UP * 0.3), run_time=1.5)
        self.wait({max(duration - 3.5, 1.0):.1f})
        self.play(FadeOut(tagline), run_time=2.0)
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


def _infographic_script(class_name, title, duration, diagram_type, images_dir):
    """Route to diagram-specific Manim scene builders."""
    builders = {
        "open_loop_mouth": _diagram_open_loop_mouth,
        "closed_loop_cycle": _diagram_closed_loop_cycle,
        "palate_zones": _diagram_palate_zones,
    }
    builder = builders.get(diagram_type, _diagram_default)
    return builder(class_name, title, duration)


def _diagram_default(class_name, title, duration):
    return f'''from manim import *

config.background_color = "{BG}"

class {class_name}(Scene):
    def construct(self):
        title = Text("{title}", color="{WHITE}").scale(0.9)
        line = Line(LEFT * 4, RIGHT * 4, color="{GOLD}", stroke_width=2)
        line.next_to(title, DOWN, buff=0.3)
        self.play(FadeIn(title), GrowFromCenter(line), run_time=1.5)
        self.wait({max(duration - 3.0, 1.0):.1f})
        self.play(FadeOut(title), FadeOut(line), run_time=1.5)
'''


def _diagram_open_loop_mouth(class_name, title, duration):
    return f'''from manim import *

config.background_color = "{BG}"

class {class_name}(Scene):
    def construct(self):
        # Title card
        title = Text("{title}", color="{WHITE}").scale(0.8)
        self.play(FadeIn(title, shift=RIGHT * 0.3), run_time=1.0)
        self.wait(0.3)
        self.play(FadeOut(title), run_time=0.5)

        # Simplified mouth cross-section — upper and lower gumline arcs
        upper_gum = Arc(radius=3.0, start_angle=PI * 0.15, angle=PI * 0.7,
                        color="{TEAL}", stroke_width=4).shift(UP * 0.5)
        lower_gum = Arc(radius=3.0, start_angle=-PI * 0.85, angle=PI * 0.7,
                        color="{TEAL}", stroke_width=4).shift(DOWN * 0.5)
        mouth = VGroup(upper_gum, lower_gum)
        mouth_label = Text("Mouth Cross-Section", color="{MUTED}", font_size=20).to_edge(UP, buff=0.4)

        self.play(Create(upper_gum), Create(lower_gum), FadeIn(mouth_label), run_time=1.5)

        # LEDs blasting fixed light — arrows pointing inward
        led_positions = [LEFT * 2 + UP * 1.2, ORIGIN + UP * 1.5, RIGHT * 2 + UP * 1.2,
                         LEFT * 2 + DOWN * 1.2, ORIGIN + DOWN * 1.5, RIGHT * 2 + DOWN * 1.2]
        arrows = VGroup()
        for pos in led_positions:
            direction = DOWN * 0.5 if pos[1] > 0 else UP * 0.5
            arrow = Arrow(pos, pos + direction, color=YELLOW, buff=0, stroke_width=3, max_tip_length_to_length_ratio=0.3)
            arrows.add(arrow)

        led_label = Text("Fixed-dose LEDs", color=YELLOW, font_size=24).to_edge(LEFT, buff=0.5).shift(DOWN * 2.5)
        self.play(FadeIn(arrows, lag_ratio=0.1), FadeIn(led_label), run_time=1.5)
        self.wait(0.5)

        # NO FEEDBACK — big red X
        no_fb = Text("NO FEEDBACK", color=RED, font_size=36, weight=BOLD)
        no_fb.move_to(ORIGIN)
        cross = Cross(stroke_color=RED, stroke_width=8).scale(0.6)
        cross.move_to(no_fb)
        self.play(FadeIn(no_fb, scale=1.3), Create(cross), run_time=1.0)
        self.wait(0.5)

        # Competitor list
        self.play(FadeOut(no_fb), FadeOut(cross), FadeOut(led_label), run_time=0.5)
        competitors = ["Lumoral", "dpl Oral Care", "Novaa", "KTS", "Starlite Smile"]
        comp_group = VGroup()
        for i, name in enumerate(competitors):
            row = VGroup(
                Text(name, color="{WHITE}", font_size=22),
                Text("No Sensing", color=RED, font_size=18),
            ).arrange(RIGHT, buff=1.0)
            comp_group.add(row)
        comp_group.arrange(DOWN, buff=0.3).move_to(DOWN * 0.5)

        self.play(FadeIn(comp_group, lag_ratio=0.15), run_time=2.0)
        wait_time = {max(duration - 9.0, 1.0):.1f}
        self.wait(wait_time)
        self.play(FadeOut(VGroup(mouth, mouth_label, arrows, comp_group)), run_time=1.0)
'''


def _diagram_closed_loop_cycle(class_name, title, duration):
    return f'''from manim import *
import numpy as np

config.background_color = "{BG}"

class {class_name}(Scene):
    def construct(self):
        # Title card
        title = Text("{title}", color="{WHITE}").scale(0.8)
        self.play(FadeIn(title, shift=RIGHT * 0.3), run_time=1.0)
        self.wait(0.3)
        self.play(FadeOut(title), run_time=0.5)

        # Mouth outline — centered left
        upper_gum = Arc(radius=2.2, start_angle=PI * 0.15, angle=PI * 0.7,
                        color="{TEAL}", stroke_width=4).shift(LEFT * 2.5 + UP * 0.3)
        lower_gum = Arc(radius=2.2, start_angle=-PI * 0.85, angle=PI * 0.7,
                        color="{TEAL}", stroke_width=4).shift(LEFT * 2.5 + DOWN * 0.3)
        mouth = VGroup(upper_gum, lower_gum)

        # LEDs + photodiodes on gumline
        led_dots = VGroup()
        pd_dots = VGroup()
        for x_off in [-1.5, 0, 1.5]:
            led = Dot(point=LEFT * 2.5 + UP * 1.3 + RIGHT * x_off * 0.8, color=YELLOW, radius=0.08)
            pd = Dot(point=LEFT * 2.5 + UP * 1.0 + RIGHT * x_off * 0.8, color="{TEAL}", radius=0.06)
            led_dots.add(led)
            pd_dots.add(pd)

        led_lbl = Text("LEDs", color=YELLOW, font_size=16).next_to(led_dots, UP, buff=0.15)
        pd_lbl = Text("Photodiodes", color="{TEAL}", font_size=16).next_to(pd_dots, DOWN, buff=0.15)

        self.play(Create(mouth), run_time=1.0)
        self.play(FadeIn(led_dots), FadeIn(pd_dots), FadeIn(led_lbl), FadeIn(pd_lbl), run_time=1.0)

        # Closed-loop cycle — right side
        steps = ["SENSE", "SCORE", "ADAPT", "LOG"]
        colors = ["{TEAL}", "{GOLD}", RED_C, BLUE_C]
        step_mobs = VGroup()
        center = RIGHT * 2.8
        for i, (step, col) in enumerate(zip(steps, colors)):
            angle = -i * TAU / 4 + TAU / 8
            pos = center + 1.5 * np.array([np.cos(angle), np.sin(angle), 0])
            box = RoundedRectangle(corner_radius=0.15, width=1.8, height=0.7,
                                    color=col, fill_color=col, fill_opacity=0.15)
            box.move_to(pos)
            label = Text(step, color=col, font_size=22, weight=BOLD).move_to(pos)
            step_mobs.add(VGroup(box, label))

        # Arrows between steps
        cycle_arrows = VGroup()
        for i in range(4):
            start = step_mobs[i].get_center()
            end = step_mobs[(i + 1) % 4].get_center()
            arrow = Arrow(start, end, color="{MUTED}", buff=0.55,
                         stroke_width=2, max_tip_length_to_length_ratio=0.15)
            cycle_arrows.add(arrow)

        self.play(FadeIn(step_mobs, lag_ratio=0.2), run_time=2.0)
        self.play(Create(cycle_arrows, lag_ratio=0.2), run_time=1.5)

        # Pulse highlight around cycle
        for i in range(2):
            for j in range(4):
                self.play(
                    step_mobs[j][0].animate.set_fill(opacity=0.4),
                    run_time=0.3,
                )
                self.play(
                    step_mobs[j][0].animate.set_fill(opacity=0.15),
                    run_time=0.3,
                )

        # $41 BOM callout
        bom = Text("$41 prototype BOM", color="{GOLD}", font_size=28, weight=BOLD)
        bom.to_edge(DOWN, buff=0.5)
        self.play(FadeIn(bom, shift=UP * 0.3), run_time=1.0)

        wait_time = {max(duration - 12.0, 0.5):.1f}
        self.wait(wait_time)
        self.play(FadeOut(VGroup(mouth, led_dots, pd_dots, led_lbl, pd_lbl,
                                 step_mobs, cycle_arrows, bom)), run_time=1.0)
'''


def _diagram_palate_zones(class_name, title, duration):
    return f'''from manim import *
import numpy as np

config.background_color = "{BG}"

class {class_name}(Scene):
    def construct(self):
        # Title card
        title = Text("{title}", color="{WHITE}").scale(0.8)
        self.play(FadeIn(title, shift=RIGHT * 0.3), run_time=1.0)
        self.wait(0.3)
        self.play(FadeOut(title), run_time=0.5)

        # Palate outline — oval top-down view
        palate = Ellipse(width=5.0, height=6.0, color="{TEAL}", stroke_width=3)
        palate.shift(LEFT * 1.5)
        palate_label = Text("Hard Palate (top-down)", color="{MUTED}", font_size=18).to_edge(UP, buff=0.4)
        self.play(Create(palate), FadeIn(palate_label), run_time=1.5)

        # 5 sensing zones
        zone_data = [
            ("1", "Upper\\nlabial", LEFT * 1.5 + UP * 2.0, "{TEAL}"),
            ("2", "Upper\\nlingual", LEFT * 1.5 + UP * 0.7, "{TEAL}"),
            ("3", "Lower\\nlabial", LEFT * 1.5 + DOWN * 0.7, "{TEAL}"),
            ("4", "Lower\\nlingual", LEFT * 1.5 + DOWN * 2.0, "{TEAL}"),
            ("5", "Palatal\\n(roof)", LEFT * 1.5 + ORIGIN, "{GOLD}"),
        ]
        zone_group = VGroup()
        for num, label_text, pos, col in zone_data:
            circle = Circle(radius=0.45, color=col, fill_color=col, fill_opacity=0.2)
            circle.move_to(pos)
            num_label = Text(num, color=col, font_size=20, weight=BOLD).move_to(pos)
            zone_group.add(VGroup(circle, num_label))

        self.play(FadeIn(zone_group, lag_ratio=0.15), run_time=2.0)

        # Advantage callouts — right side
        advantages = [
            "No melanin bias",
            "Thin epithelium (0.2mm)",
            "Rich perfusion",
            "Zero ambient light",
        ]
        callout_group = VGroup()
        for i, adv in enumerate(advantages):
            check = Text("\\u2713", color=GREEN, font_size=22)
            text = Text(adv, color="{WHITE}", font_size=20)
            row = VGroup(check, text).arrange(RIGHT, buff=0.3)
            callout_group.add(row)
        callout_group.arrange(DOWN, buff=0.35, aligned_edge=LEFT).move_to(RIGHT * 3 + UP * 1.0)

        self.play(FadeIn(callout_group, lag_ratio=0.3), run_time=2.5)
        self.wait(0.5)

        # Biomarker scroll
        biomarkers = ["SpO2", "Heart Rate", "HRV", "Hemoglobin", "Bilirubin", "Inflammation"]
        bio_group = VGroup()
        for bm in biomarkers:
            dot = Dot(color="{GOLD}", radius=0.05)
            text = Text(bm, color="{GOLD}", font_size=18)
            row = VGroup(dot, text).arrange(RIGHT, buff=0.2)
            bio_group.add(row)
        bio_group.arrange(DOWN, buff=0.25, aligned_edge=LEFT).move_to(RIGHT * 3 + DOWN * 1.8)

        self.play(FadeIn(bio_group, lag_ratio=0.15), run_time=2.0)

        wait_time = {max(duration - 11.5, 0.5):.1f}
        self.wait(wait_time)
        self.play(FadeOut(VGroup(palate, palate_label, zone_group,
                                 callout_group, bio_group)), run_time=1.0)
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


# ---------------------------------------------------------------------------
# Clip-based rendering (new pipeline)
# ---------------------------------------------------------------------------

PACING_BUFFER = {"tight": 0.5, "normal": 1.5, "breathe": 3.5}


def _parse_direction(direction: str) -> tuple[str, dict]:
    """Parse 'primitive_name(k=v, k=v)' into (name, params_dict).

    Returns ("", {}) if direction doesn't match the pattern.
    List values use bracket syntax: [a,b,c]
    """
    import re
    match = re.match(r'(\w+)\((.+)\)$', direction.strip(), re.DOTALL)
    if not match:
        return ("", {})

    name = match.group(1)
    params_str = match.group(2)
    params = {}

    # Split on commas not inside brackets
    parts = re.split(r',\s*(?![^\[]*\])', params_str)
    for part in parts:
        if '=' not in part:
            continue
        key, val = part.split('=', 1)
        key = key.strip()
        val = val.strip()
        # Parse list values
        if val.startswith('[') and val.endswith(']'):
            val = [v.strip() for v in val[1:-1].split(',')]
        # Parse numeric values
        elif val.replace('.', '').replace('-', '').isdigit():
            val = float(val) if '.' in val else int(val)
        params[key] = val

    return (name, params)


# Animation primitive dispatch table
ANIM_PRIMITIVES = {
    "counter", "fingerprint_compare", "sonar_ring", "anchor_drop",
    "dot_field", "remove_reveal", "dot_merge", "bar_chart",
    "before_after", "organism_reveal",
}


def build_clip_script(clip: dict, theme_name: str, duration: float,
                      images_dir: str, chapter_num: str = None,
                      chapter_title: str = None) -> str:
    """Generate a Manim script for a single clip using the theme's three-layer system."""
    from docugen.themes import load_theme
    theme = load_theme(theme_name)

    # Handle legacy flat visuals format — convert to three-layer
    visuals = clip.get("visuals", {})
    if "choreography" not in visuals and "theme_elements" not in visuals:
        # Legacy format: convert type + direction to choreography
        vis_type = visuals.get("type", "blank")
        direction = visuals.get("direction", "")
        assets = visuals.get("assets", [])

        clip = dict(clip)  # don't mutate original
        clip["visuals"] = {
            "theme_elements": ["hex_grid", "imperial_border", "floating_bg"],
            "content": {"assets": assets, "placement": "center"},
            "choreography": {},
        }

        if vis_type == "chapter_card":
            clip["visuals"]["choreography"] = {
                "type": "chapter_card",
                "params": {"num": chapter_num or "00", "title": chapter_title or "UNTITLED"},
            }
            clip["visuals"]["content"]["assets"] = []
        elif vis_type == "animation" and direction:
            prim_name, params = _parse_direction(direction)
            if prim_name and prim_name in ANIM_PRIMITIVES:
                clip["visuals"]["choreography"] = {"type": prim_name, "params": params}
            else:
                clip["visuals"]["choreography"] = {}
        elif vis_type == "image_reveal":
            pass  # content layer handles assets
        elif vis_type == "data_reveal" and direction:
            clip["visuals"]["choreography"] = {
                "type": "data_text", "params": {"text": direction},
            }

    return theme.build_scene(clip, duration, images_dir,
                             chapter_num=chapter_num or "00",
                             chapter_title=chapter_title or "")


def render_clip(project_path: Path, clip: dict, theme_name: str,
                chapter_num: str, chapter_title: str) -> str:
    """Render a single clip to MP4."""
    project_path = Path(project_path)
    config = load_config(project_path)
    clip_id = clip["clip_id"]
    images_dir = project_path / "images"
    clips_dir = project_path / "build" / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    media_dir = clips_dir / "media"

    out_mp4 = clips_dir / f"{clip_id}.mp4"
    if out_mp4.exists():
        return str(out_mp4)

    # Get duration from timing model (computed by direct_apply)
    timing = clip.get("timing", {})
    duration = timing.get("clip_duration", 0)

    # Fallback: measure WAV if timing not yet computed
    if duration <= 0:
        wav_path = project_path / "build" / "narration" / f"{clip_id}.wav"
        if wav_path.exists():
            duration = _get_wav_duration(wav_path)
        else:
            duration = 3.0
        pacing = clip.get("pacing", "normal")
        duration += PACING_BUFFER.get(pacing, 1.5)

    script = build_clip_script(
        clip, theme_name, duration, str(images_dir),
        chapter_num=chapter_num, chapter_title=chapter_title,
    )
    class_name = f"Scene_{clip_id}"
    script_path = clips_dir / f"_scene_{clip_id}.py"
    script_path.write_text(script)

    fps = config["video"]["fps"]
    quality = "-qh" if fps >= 60 else "-qm"

    # Clean stale cached renders for this clip
    for stale in media_dir.rglob(f"{class_name}.mp4"):
        stale.unlink(missing_ok=True)

    result = subprocess.run(
        ["manim", quality, str(script_path.resolve()), class_name,
         "--media_dir", str(media_dir.resolve()), "--format", "mp4"],
        capture_output=True, text=True,
    )

    if result.returncode != 0:
        script_path.unlink(missing_ok=True)
        raise RuntimeError(f"Manim render failed for {clip_id}:\n{result.stderr[-500:]}")

    output_files = sorted(media_dir.rglob(f"{class_name}.mp4"),
                          key=lambda p: p.stat().st_mtime, reverse=True)
    if not output_files:
        script_path.unlink(missing_ok=True)
        raise FileNotFoundError(f"Manim output not found for {class_name}")

    output_files[0].rename(out_mp4)
    script_path.unlink(missing_ok=True)
    return str(out_mp4)


def _render_from_clips(project_path: Path) -> str:
    """Render all clips from clips.json."""
    config = load_config(project_path)
    clips_data = json.loads((project_path / "build" / "clips.json").read_text())
    theme_name = clips_data.get("theme", config.get("theme", "biopunk"))

    results = []
    for i, chapter in enumerate(clips_data["chapters"]):
        ch_num = f"{i:02d}"
        ch_title = chapter.get("title", "").upper()
        for clip in chapter["clips"]:
            clip_id = clip["clip_id"]
            out_mp4 = project_path / "build" / "clips" / f"{clip_id}.mp4"
            if out_mp4.exists():
                results.append(f"{clip_id}.mp4 (exists)")
                continue
            try:
                render_clip(project_path, clip, theme_name, ch_num, ch_title)
                results.append(f"{clip_id}.mp4 (rendered)")
            except Exception as e:
                results.append(f"{clip_id}.mp4 (FAILED: {e})")

    return "Rendered clips:\n" + "\n".join(results)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def render_all(project_path: str | Path) -> str:
    """Render video clips.

    Uses clips.json if available (per-clip, theme-dispatched).
    Falls back to plan.json (per-chapter, legacy).
    """
    project_path = Path(project_path)

    clips_path = project_path / "build" / "clips.json"
    if clips_path.exists():
        return _render_from_clips(project_path)

    # Legacy chapter-based rendering
    config = load_config(project_path)
    plan_path = project_path / "build" / "plan.json"
    if not plan_path.exists():
        raise FileNotFoundError("No clips.json or plan.json found.")

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
