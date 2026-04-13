# Three-Layer Rendering Design

> Separate theme (background), content (assets), and choreography (animation)
> into independent layers that compose in every clip.

---

## Problem

The current render system collapsed theme, content, and choreography into a single dispatch. Result:
- 96 of 113 clips are just floating dots on black — no hex grid, no imperial brackets, no DNA helices
- The original hand-crafted sequences (intro particle field, anchor drop sonar, rapamycin removal) were lost in the refactor
- Animation primitives work but they each rebuild the background from scratch, inconsistently

## Solution

Every clip renders three layers that compose top to bottom:

```
┌─────────────────────────────────┐
│  CHOREOGRAPHY (direction)       │  Animated content — primitives, freestyle
│  CONTENT (assets)               │  SVGs, photos, data text — static or Ken Burns
│  THEME (theme_elements)         │  Hex grid, borders, DNA, particles — always present
└─────────────────────────────────┘
```

The Manim scene for every clip:
1. Adds theme background elements (from `theme_elements` list)
2. Places content assets (from `assets` list)
3. Runs choreography animation (from `direction`)
4. Fills remaining time with ambient motion

---

## Data Model Change

### clips.json — updated clip format

```json
{
  "clip_id": "ch4_anchor_08",
  "text": "Ginsenoside Rb1 — 226 others.",
  "exaggeration": 0.55,
  "emotion_tag": "dramatic",
  "pacing": "breathe",
  "visuals": {
    "theme_elements": ["hex_grid", "imperial_border", "floating_bg"],
    "content": {
      "assets": ["pres-anchor-yield.svg"],
      "placement": "left"
    },
    "choreography": {
      "type": "anchor_drop",
      "params": {"name": "Ginsenoside Rb1", "count": 226, "color": "gold"}
    }
  }
}
```

### Layer 1: theme_elements

Available elements (theme provides the implementation):

| Element | Description |
|---------|-------------|
| `hex_grid` | Imperial hexagonal grid, low opacity |
| `imperial_border` | Corner bracket HUD frame |
| `floating_bg` | Drifting colored dots for ambient motion |
| `dna_helix` | Flanking DNA double helices |
| `particle_field` | Dense bioluminescent spore field |
| `scanline` | Periodic horizontal scanner sweep |

Default for most clips: `["hex_grid", "imperial_border", "floating_bg"]`

Intro/outro get the full set: `["hex_grid", "imperial_border", "floating_bg", "dna_helix", "particle_field"]`

Chapter cards: `["hex_grid", "imperial_border", "floating_bg"]`

Dark/minimal clips (ch5): `["floating_bg"]` only

### Layer 2: content

| Field | Description |
|-------|-------------|
| `assets` | List of filenames to display (SVG, JPG, PNG) |
| `placement` | Where to place: `center`, `left`, `right`, `full` (default: `center`) |

Assets are placed on top of the theme layer. Ken Burns zoom applied automatically. If `placement` is `left`, content goes on the left half and leaves room for text/data on the right.

If `assets` is empty, this layer is skipped.

### Layer 3: choreography

| Field | Description |
|-------|-------------|
| `type` | Primitive name, `chapter_card`, `freestyle`, or empty |
| `params` | Dict of parameters for the primitive |

If `type` is empty or missing, no choreography — just theme + content + ambient hold.

If `type` is `chapter_card`, renders the chapter number + title with throb.

If `type` is `freestyle`, `params.code` contains raw Manim code to inject.

If `type` is a primitive name, dispatches to `theme.anim_*` method — but the primitive now only generates the foreground animation code (not background), because the theme layer already provides the background.

---

## Theme Interface Change

### Current (broken)
Each `anim_*` method builds the entire scene including background. This means:
- Duplicate background code in every primitive
- Inconsistent backgrounds between primitives
- No way to compose content + choreography

### New (three-layer)
The theme provides:

```python
class ThemeBase:
    def build_scene(self, clip, duration, images_dir) -> str:
        """Build complete Manim script for a clip using three layers."""

    def render_theme_layer(self, elements: list[str]) -> str:
        """Return Manim code that sets up background elements."""

    def render_content_layer(self, assets, placement, images_dir) -> str:
        """Return Manim code that places content assets."""

    def render_choreography(self, choreo_type, params, duration) -> str:
        """Return Manim code for the animation choreography."""
```

`build_scene` composes all three:
1. Writes the manim header (imports, palette, helpers)
2. Opens a Scene class
3. Calls `render_theme_layer` — adds background elements
4. Calls `render_content_layer` — places assets
5. Calls `render_choreography` — runs animation
6. Fills remaining time with `alive_wait`

Each `render_*` method returns raw Manim code (indented, ready to paste into construct body). They don't create scene classes — `build_scene` wraps them.

### Theme elements registry

```python
THEME_ELEMENTS = {
    "hex_grid": "grid = make_hex_grid(...)\n        self.add(grid)",
    "imperial_border": "border = imperial_border()\n        self.add(border)",
    "floating_bg": "bg = make_floating_bg()\n        self.add(bg)",
    "dna_helix": "dna_l = make_dna_helix().shift(LEFT*6)...\n        self.add(dna_l, dna_r)",
    "particle_field": "particles = make_particle_field(n=300)\n        self.add(particles)",
}
```

### Choreography still uses primitives

The `anim_*` methods stay but their signature changes — they return indented code blocks (not complete scene scripts). `build_scene` handles the scene wrapper.

---

## Updated Split Algorithm

The split tool needs to assign `theme_elements` per clip. Rules:

- Chapter cards: `["hex_grid", "imperial_border", "floating_bg"]`
- Intro/outro clips: `["hex_grid", "imperial_border", "floating_bg", "dna_helix", "particle_field"]`
- ch5_dark clips: `["floating_bg"]` (minimal, dark)
- Everything else: `["hex_grid", "imperial_border", "floating_bg"]`

The split tool also now populates `choreography.type` and `choreography.params` (moved from the flat `direction` string to a structured dict).

---

## Render Pipeline Change

`build_clip_script` simplifies to:
1. Load theme
2. Call `theme.build_scene(clip, duration, images_dir)`
3. Rename class to `Scene_{clip_id}`
4. Return script

The render tool no longer parses direction strings or dispatches — the theme does all of that internally.

---

## Migration

1. Update `ThemeBase` with new `build_scene`, `render_theme_layer`, `render_content_layer`, `render_choreography`
2. Rewrite `BiopunkTheme` to implement three-layer composition
3. Move primitive methods to return code blocks instead of full scenes
4. Update `split.py` to produce the new visuals format
5. Simplify `build_clip_script` in render.py
6. Update clips.json for parse-evols-yeast
7. Re-render and stitch

---

## Out of Scope

- Layer opacity/blending controls (all layers at full opacity)
- Per-element parameter overrides in theme_elements (hex_grid always uses theme defaults)
- Audio-reactive choreography (animation doesn't respond to narration waveform)
