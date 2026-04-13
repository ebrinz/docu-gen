# Perilux Documentary Infographic Upgrade

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the Perilux documentary from text-card visuals to animated Manim infographics, swap the banner in as the intro, switch to a hype used-car-salesman voice, and rewrite the narration copy.

**Architecture:** Add new scene-type functions in `render.py` for infographic diagrams (mouth cross-section, closed-loop animation, palate zone map) and a banner-reveal intro. Update `plan.json` with new `scene_type: "infographic"` chapters that carry a `diagram_type` field to select which diagram to render. Switch voice to `fable` in `config.yaml` and rewrite narration copy for energy.

**Tech Stack:** Manim (Python animation), OpenAI TTS (`fable` voice), existing docugen pipeline

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/docugen/tools/render.py` | Modify | Add `_banner_intro_script`, `_infographic_script`, and 3 diagram builders |
| `projects/perilux/build/plan.json` | Rewrite | New narration copy, scene types, diagram assignments |
| `projects/perilux/config.yaml` | Modify | Switch voice to `fable` |

---

### Task 1: Update config and rewrite plan.json

**Files:**
- Modify: `projects/perilux/config.yaml`
- Rewrite: `projects/perilux/build/plan.json`

- [ ] **Step 1: Switch voice to fable in config.yaml**

```yaml
title: "Perilux — Closed-Loop Oral Biofeedback"
voice:
  model: tts-1-hd
  voice: fable
video:
  resolution: 1080p
  fps: 60
drone:
  cutoff_hz: 350
  duck_db: -20
  rt60: 2.0
  cue_freq: 180
```

- [ ] **Step 2: Rewrite plan.json with hype narration and infographic scene types**

```json
{
  "title": "Perilux: Revolutionizing Oral Health Monitoring",
  "chapters": [
    {
      "id": "intro",
      "title": "Introducing Perilux",
      "narration": "Ladies and gentlemen, what if I told you that every single oral light therapy device on the market right now is flying completely blind? That's right — blind! They blast your gums with light and hope for the best. No feedback. No adaptation. Nothing. Well, buckle up — because Perilux is about to change everything.",
      "scene_type": "banner_intro",
      "images": ["banner.png"],
      "duration_estimate": 18.0
    },
    {
      "id": "ch1",
      "title": "The Problem",
      "narration": "Here's the dirty secret of the oral health industry. Every device out there — Lumoral, dpl Oral Care, Novaa — they all do the same thing: fixed dose, fixed time, zero feedback. They don't know if your tissue is inflamed. They don't know if they're under-dosing or over-dosing. It's like driving with your eyes closed. And folks, that's a two hundred million dollar market just waiting to be disrupted.",
      "scene_type": "infographic",
      "diagram_type": "open_loop_mouth",
      "images": [],
      "duration_estimate": 22.0
    },
    {
      "id": "ch2",
      "title": "The Breakthrough",
      "narration": "Perilux doesn't guess — it knows. Photodiodes right next to the therapy LEDs sense your tissue oxygenation in real time. Inflamed? It cranks up the healing light. Healthy? It backs off to maintenance dose. Every five seconds, every gumline zone — sense, score, adapt, log. This is the world's first closed-loop oral biofeedback device, and it fits in your hand for forty-one dollars in parts.",
      "scene_type": "infographic",
      "diagram_type": "closed_loop_cycle",
      "images": [],
      "duration_estimate": 25.0
    },
    {
      "id": "ch3",
      "title": "The Secret Weapon",
      "narration": "But here's where it gets really wild. The roof of your mouth — the hard palate — is arguably the best non-invasive optical sensing site on the entire human body. No melanin bias. Paper-thin epithelium. Rich blood flow from the palatine artery. And when your mouth is closed? Zero ambient light interference. That means Perilux doesn't just treat your gums — it tracks your SpO2, heart rate, HRV, hemoglobin trends, even bilirubin. Through. Your. Mouth.",
      "scene_type": "infographic",
      "diagram_type": "palate_zones",
      "images": [],
      "duration_estimate": 28.0
    },
    {
      "id": "outro",
      "title": "The Future Starts Here",
      "narration": "The first device that sees your inflammation, treats it, and tracks your systemic health — through your mouth. Perilux. Coming soon.",
      "scene_type": "banner_outro",
      "images": ["banner.png"],
      "duration_estimate": 10.0
    }
  ]
}
```

- [ ] **Step 3: Delete existing narration WAVs so they regenerate fresh**

Run: `rm projects/perilux/build/narration/*.wav`

---

### Task 2: Add banner intro and outro scene types to render.py

**Files:**
- Modify: `src/docugen/tools/render.py`

- [ ] **Step 1: Add `_banner_intro_script` function after existing `_intro_script`**

This replaces the text title with the banner PNG — dramatic fade-in with slow Ken Burns zoom, then the subtitle text animates on top.

```python
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
```

- [ ] **Step 2: Add `_banner_outro_script` function after `_banner_intro_script`**

Banner fades back in with the closing tagline overlaid.

```python
def _banner_outro_script(class_name, doc_title, title, duration, images, images_dir):
    """Outro scene with banner image and closing tagline."""
    images_dir_str = str(images_dir).replace("\\", "\\\\")
    banner = images[0] if images else "banner.png"
    title_esc = title.replace('"', '\\"')

    return f'''from manim import *
from pathlib import Path

config.background_color = "{BG}"

class {class_name}(Scene):
    def construct(self):
        img_path = Path("{images_dir_str}") / "{banner}"
        banner = ImageMobject(str(img_path))
        banner.height = 7.0
        banner.width = 12.0
        banner.set_opacity(0.6)

        tagline = Text("{title_esc}", color="{GOLD}").scale(0.8)
        tagline.move_to(ORIGIN)

        self.play(FadeIn(banner), run_time=1.5)
        self.play(FadeIn(tagline, shift=UP * 0.3), run_time=1.5)
        self.wait({max(duration - 5.0, 1.0):.1f})
        self.play(FadeOut(tagline), FadeOut(banner), run_time=2.0)
'''
```

- [ ] **Step 3: Update `build_manim_script` routing to handle new scene types**

Add cases for `banner_intro`, `banner_outro`, and `infographic` in the routing function:

```python
def build_manim_script(chapter: dict, doc_title: str, duration: float,
                       images_dir: Path) -> str:
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
```

- [ ] **Step 4: Verify render.py parses without errors**

Run: `cd /Users/crashy/Development/docu-mentation && .venv/bin/python -c "from docugen.tools.render import build_manim_script; print('OK')"`
Expected: `OK`

---

### Task 3: Add infographic scene type with 3 diagram builders

**Files:**
- Modify: `src/docugen/tools/render.py`

This is the core visual upgrade. One dispatcher function `_infographic_script` routes to diagram-specific builders based on `diagram_type`.

- [ ] **Step 1: Add `_infographic_script` dispatcher**

```python
def _infographic_script(class_name, title, duration, diagram_type, images_dir):
    """Route to diagram-specific Manim scene builders."""
    builders = {
        "open_loop_mouth": _diagram_open_loop_mouth,
        "closed_loop_cycle": _diagram_closed_loop_cycle,
        "palate_zones": _diagram_palate_zones,
    }
    builder = builders.get(diagram_type, _diagram_default)
    return builder(class_name, title, duration)
```

- [ ] **Step 2: Add `_diagram_default` fallback**

Simple chapter card with a subtle accent line — used if diagram_type is unrecognized:

```python
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
```

- [ ] **Step 3: Add `_diagram_open_loop_mouth` — ch1 "The Problem"**

Animated mouth cross-section showing dumb LEDs blasting fixed light. Red X appears. Competitor names scroll through with "No Sensing" labels.

```python
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
```

- [ ] **Step 4: Add `_diagram_closed_loop_cycle` — ch2 "The Breakthrough"**

Mouth diagram with the SENSE → SCORE → ADAPT → LOG cycle animating around it. LED intensity pulses.

```python
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
        positions = [UR * 1.2, DR * 1.2, DL * 1.2 + RIGHT * 5, UL * 1.2 + RIGHT * 5]
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
```

- [ ] **Step 5: Add `_diagram_palate_zones` — ch3 "The Secret Weapon"**

Top-down palate view with 5 numbered sensing zones, callout labels animating in, and biomarker list.

```python
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
```

- [ ] **Step 6: Verify render.py parses cleanly**

Run: `cd /Users/crashy/Development/docu-mentation && .venv/bin/python -c "from docugen.tools.render import build_manim_script; print('OK')"`
Expected: `OK`

---

### Task 4: Regenerate narration, render, and stitch

After all code changes are saved:

- [ ] **Step 1: Restart MCP server**

User must run `/mcp` in Claude Code to reload the server with new code.

- [ ] **Step 2: Delete old narration**

Run: `rm projects/perilux/build/narration/*.wav`

- [ ] **Step 3: Run narrate**

Run MCP tool: `narrate(project_path="projects/perilux")`

Expected: 5 WAVs with `fable` voice, punchy delivery, ~86-100s total.

- [ ] **Step 4: Run render**

Run MCP tool: `render(project_path="projects/perilux")`

Expected: 5 clips — banner intro, 3 infographic chapters, banner outro.

- [ ] **Step 5: Run stitch**

Run MCP tool: `stitch(project_path="projects/perilux")`

Expected: `build/final.mp4` under 2 minutes.

- [ ] **Step 6: Open and review**

Run: `open projects/perilux/build/final.mp4`
