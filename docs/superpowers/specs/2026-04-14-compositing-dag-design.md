# Compositing DAG Render Architecture

**Date:** 2026-04-14
**Status:** Design approved, pending implementation
**Scope:** Replace monolithic render pipeline with a compositing DAG that supports pluggable renderers, node-level caching, and multi-tool creative workflows.

---

## Problem

The current render pipeline has two rendering paths that produce different results:

1. **Three-layer path** (theme + content + choreography) — produces biopunk-themed visuals with hex grids, imperial borders, and particles. But `render_choreography()` only receives `(params, duration)` — no `word_times`, no `cue_words`, no timing data.

2. **Bespoke builder path** — `_build_*_scene` methods that short-circuit the three-layer system. They have word-level sync and cue timing but produce bare visuals on black backgrounds with no theme layers.

Neither path produces the intended output. 55+ of 82 clips render without theme visuals. The choreography methods that include theme elements (`_choreo_*`) are orphaned — never called because bespoke builders take priority.

Beyond this immediate bug, the architecture is closed to non-Manim tools. There is no way to add post-processing passes, shader-based layers, AI enhancement, or per-clip sound design without restructuring.

## Solution

Replace the monolithic render with a **compositing DAG** per clip. Each node in the DAG has a renderer type, inputs from upstream nodes, and produces a visual or audio artifact. An orchestrator walks the DAG, dispatches nodes to their renderers, and pipes outputs forward.

Manim becomes one renderer among potentially many. When adjacent Manim nodes reference each other, they fuse into a single Scene for performance. Non-Manim nodes (ffmpeg, shaders, AI, audio) participate as peers.

---

## Architecture

### The Render DAG

Every clip gets a directed acyclic graph of render nodes. Each node:

- Has a `name` (unique within the clip)
- Has a `renderer` type (registered callable)
- May declare `inputs` (upstream node names whose outputs it consumes)
- May declare `refs` (upstream node names whose Manim objects it needs live access to — triggers fusion)
- Produces an output file (MP4, PNG, image sequence directory, or WAV)

Example DAG for a `photo_organism` clip:

```yaml
nodes:
  bg:
    renderer: manim_theme
    elements: [hex_grid, imperial_border, floating_bg]
  content:
    renderer: static_asset
    asset: yeast_micro.jpg
    layout: left_third
  choreo:
    renderer: manim_choreo
    refs: [bg, content]
  audio_cues:
    renderer: audio_synth
    cue_words: [from clip]
  composite:
    renderer: ffmpeg_composite
    inputs: [bg+content+choreo]
    blend: [normal, normal, normal]
  post:
    renderer: ffmpeg_post
    inputs: [composite]
    audio: [audio_cues]
    filters: []
```

### The Orchestrator (`compose.py`)

New module that replaces the current render dispatch logic.

**Responsibilities:**

1. **Read the clip's DAG** from `clips.json` (or generate a default via the theme's `default_dag()`)
2. **Topological sort** the nodes
3. **Check cache** for each node — content hash of (node definition + input hashes) compared to cached output
4. **Detect fusion opportunities** — adjacent manim nodes with `refs` between them
5. **Dispatch** each uncached node to its registered renderer
6. **Pipe outputs** — each node's output path is available to downstream nodes via `inputs` dict
7. **Final output** — terminal node's output becomes the clip MP4

**Renderer interface:**

```python
def render_node(
    node: dict,
    inputs: dict[str, Path],
    clip: dict,
    project_path: Path,
) -> Path:
    """
    node: DAG node definition (renderer, params, refs, etc.)
    inputs: {upstream_node_name: path_to_output}
    clip: full clip dict (clip_id, text, word_times, visuals with
          cue_words, timing, pacing — everything)
    project_path: for resolving assets, build dirs

    Returns: path to output file
    """
```

### Node-Level Caching

Each node's output is stored at:

```
build/clips/{clip_id}/_node_{node_name}.{ext}
```

A content hash is computed from:
- The node definition (renderer, params, elements, filters, etc.)
- The hashes of all input nodes' outputs
- Relevant clip data (word_times, cue_words for choreo nodes; asset file mtimes for content nodes)

If the hash matches the cached output, the node is skipped. This means:
- Re-rendering a single imperfect node only re-runs that node + downstream compositing
- Manually replacing a node's output file is picked up by the compositor
- Changing a cue_word timing only invalidates the choreo node, not the theme bg

### Manim Fusion

When the orchestrator detects adjacent Manim nodes with `refs` between them, it fuses them into a single Manim Scene.

**Fusion criteria:**
- Two or more nodes use `manim_theme` or `manim_choreo` renderers
- A downstream node declares `refs` to an upstream node
- No non-manim node sits between them in the DAG

**Fused scene structure:**

```python
class Scene_{clip_id}(Scene):
    def construct(self):
        self.layers = {}

        # === Layer: bg (manim_theme) ===
        grid = make_hex_grid()
        self.add(grid)
        border = imperial_border()
        self.add(border)
        bg = make_floating_bg()
        self.add(bg)
        self.layers['bg'] = {'grid': grid, 'border': border, 'particles': bg}

        # === Layer: content (static_asset, injected into scene) ===
        photo = ImageMobject("images/yeast_micro.jpg")
        photo.height = 4.0
        photo.move_to(LEFT * 2.5)
        photo_frame = SurroundingRectangle(photo, ...)
        self.play(FadeIn(photo), Create(photo_frame))
        self.layers['content'] = {'photo': photo, 'frame': photo_frame}

        # === Layer: choreo (manim_choreo, refs: [bg, content]) ===
        frame = self.layers['content']['frame']
        self.wait(2.3)  # word_times sync
        lbl = Text("S. cerevisiae", color=GOLD)
        pointer = Line(frame.get_right(), lbl.get_left(), color=GOLD)
        self.play(Create(pointer), FadeIn(lbl))
```

**The `self.layers` contract:**
- Each layer writes to `self.layers[node_name]` — a dict of named Manim mobjects
- Downstream layers read from `self.layers[ref_name]` to get live object references
- The fuser concatenates code blocks in DAG order with `self.layers = {}` at the top

**Static asset nodes in fused scenes:** When a `static_asset` node is referenced by a fused manim node, its placement logic is inlined into the fused Scene as Manim `ImageMobject` code (as shown in the example above). The static_asset renderer only runs independently when it is NOT part of a fused group.

**Graceful degradation when fusion is not possible** (non-manim node between manim nodes):
- Each manim node renders independently to MP4 with alpha
- Cross-layer refs degrade from live mobject references to positioned images
- The content node's output image is injected as an `ImageMobject` with layout position from node params
- Pointer positions use declared layout coordinates instead of `.get_right()`

---

## Theme Interface

Themes change from monolithic scene builders to **providers of renderer implementations and DAG templates**.

### New `ThemeBase` interface

```python
class ThemeBase(ABC):
    name: str
    palette: dict[str, str]

    @abstractmethod
    def default_dag(self, clip: dict) -> list[dict]:
        """Return the default DAG node list for a clip.

        Theme decides what layers a clip needs based on
        slide_type, assets, cue_words, etc. Can vary per clip.
        """

    @abstractmethod
    def render_theme_layer(self, node: dict, inputs: dict[str, Path],
                           clip: dict, project_path: Path) -> Path:
        """Render background elements to MP4 with alpha."""

    @abstractmethod
    def render_choreography(self, node: dict, inputs: dict[str, Path],
                            clip: dict, project_path: Path) -> Path:
        """Render animated content.

        Has access to full clip dict (word_times, cue_words)
        and upstream node outputs via inputs dict.
        When fused, has access to self.layers for live mobject refs.
        """

    @abstractmethod
    def render_content(self, node: dict, inputs: dict[str, Path],
                       clip: dict, project_path: Path) -> Path:
        """Place static assets at layout positions."""

    # Audio (unchanged)
    @abstractmethod
    def transition_sounds(self) -> dict[str, callable]: ...

    @abstractmethod
    def chapter_layers(self) -> dict[str, callable]: ...
```

### What's removed from `ThemeBase`

- `build_scene()` — replaced by orchestrator + DAG dispatch
- `_get_slide_builder()` — bespoke builder dispatch mechanism gone
- Bridge conversion (old format → new format translation) — gone
- Legacy wrappers (`idle_scene`, `chapter_card`, `image_reveal`, `data_reveal`, `custom_animation`) — gone

### Biopunk theme changes

**Removed (~280 lines):**
- `_build_title_scene`
- `_build_chapter_card_scene`
- `_build_data_text_scene`
- `_build_ambient_field_scene`
- `_build_photo_organism_scene`
- `_build_counter_sync_scene`

**Rewritten choreography methods** — each `_choreo_*` method gains:
- Full `clip` dict access (word_times, cue_words with at_index and event sequencing)
- `self.layers` access for cross-layer mobject references when fused
- All features from the bespoke builders migrated in

**Feature parity (nothing lost):**

| Feature | Old location | New location |
|---|---|---|
| Word-level counter sync | `_build_counter_sync_scene` | `_choreo_counter` via `clip["word_times"]` |
| Multi-line bullet stagger | `_build_data_text_scene` | `_choreo_data_text` via `clip["word_times"]` |
| HUD border + cue-synced pointers | `_build_photo_organism_scene` | `_choreo_organism_reveal` via `self.layers["content"]` |
| Plan.json title integration | `_build_title_scene` | `_choreo_title` delegates to title tool |
| Theme bg on every slide | Three-layer path only | Every clip — `manim_theme` node always present in DAG |

---

## Renderer Plugin System

### Registry

```python
# compose.py
RENDERERS: dict[str, Callable] = {}

def register_renderer(name: str, fn: Callable):
    RENDERERS[name] = fn
```

### Auto-discovery

All modules in `src/docugen/renderers/` are imported at orchestrator init. Each module calls `register_renderer()` at import time.

### Day-one renderers

| Renderer | Module | Purpose |
|---|---|---|
| `manim_theme` | `renderers/manim_theme.py` | Theme background layer (hex grid, particles, border) |
| `manim_choreo` | `renderers/manim_choreo.py` | Choreography with full clip context + self.layers refs |
| `manim_fused` | `renderers/manim_fused.py` | Internal — handles fused multi-manim-node scenes |
| `static_asset` | `renderers/static_asset.py` | Image placement at layout position |
| `ffmpeg_composite` | `renderers/ffmpeg_composite.py` | Alpha-composite inputs with blend modes |
| `ffmpeg_post` | `renderers/ffmpeg_post.py` | Filter chain (bloom, vignette, color grade) |
| `audio_synth` | `renderers/audio_synth.py` | Current numpy synth (wraps existing drone.py) |

### Future renderers (architecture supports, not built now)

| Renderer | Purpose | Technology |
|---|---|---|
| `shader` | Procedural backgrounds, particle systems | GLSL / Metal Compute |
| `ai_upscale` | Resolution enhancement | Real-ESRGAN or API |
| `ai_style` | Style transfer passes | Stable Diffusion img2img |
| `lottie` | Motion graphics from AE exports | lottie-renderer |
| `audio_clap` | CLAP-based SFX retrieval from local library | LAION CLAP embeddings |
| `audio_gen` | Text-to-SFX generation | AudioGen / Sony Woosh |
| `audio_post` | Audio effects chain | Spotify Pedalboard / Supriya |

### Adding a new renderer

```python
# renderers/ai_upscale.py
from docugen.compose import register_renderer

def render_node(node, inputs, clip, project_path):
    input_path = inputs[node["inputs"][0]]
    output_path = (project_path / "build" / "clips" /
                   clip["clip_id"] / f"_node_{node['name']}.mp4")
    # ... call upscaler ...
    return output_path

register_renderer("ai_upscale", render_node)
```

---

## Audio Architecture

### Per-clip audio via DAG

The DAG supports optional `audio_*` nodes for per-clip sound design. These produce WAV files that get muxed into the clip during the `ffmpeg_post` step.

```yaml
audio_cues:
  renderer: audio_synth
  cue_words: [from clip visuals]
```

### Tiered SFX resolver (future)

When audio renderers are built out, per-clip sound design uses a tiered resolution strategy:

1. **CLAP retrieval** — search local SFX library by semantic description (fastest, most predictable)
2. **Freesound API** — wider library search + CLAP re-rank (for sounds not in local library)
3. **AudioGen/Woosh** — text-to-SFX generation (for novel sounds)
4. **Procedural synthesis** — Supriya/numpy for precisely defined tonal sounds
5. **Post-processing** — Pedalboard effects chain to match theme aesthetic

### Global audio pipeline unchanged

`score.py` (full-documentary drone), `stitch.py` (final assembly with voice ducking), `narrate.py` (TTS), and `audio_fx.py` (post-FX) remain as-is. Per-clip audio from DAG nodes is mixed in during stitch alongside narration and score.

---

## File Changes

### New files

| File | Purpose |
|---|---|
| `src/docugen/compose.py` | Orchestrator — DAG walker, fusion, caching, dispatch |
| `src/docugen/renderers/__init__.py` | Auto-discovery and renderer registration |
| `src/docugen/renderers/manim_theme.py` | Theme background renderer |
| `src/docugen/renderers/manim_choreo.py` | Choreography renderer |
| `src/docugen/renderers/manim_fused.py` | Fused multi-manim-node renderer |
| `src/docugen/renderers/static_asset.py` | Static image placement renderer |
| `src/docugen/renderers/ffmpeg_composite.py` | Alpha compositing renderer |
| `src/docugen/renderers/ffmpeg_post.py` | Post-processing filter renderer |
| `src/docugen/renderers/audio_synth.py` | Numpy synth renderer (wraps drone.py) |

### Modified files

| File | Change |
|---|---|
| `themes/base.py` | New interface: `default_dag()`, renderer methods. Remove `build_scene()`, bridge conversion, bespoke dispatch, legacy wrappers |
| `themes/biopunk.py` | Remove 6 `_build_*_scene` methods (~280 lines). Rewrite `_choreo_*` methods with full clip access + self.layers. Add `default_dag()` |
| `tools/render.py` | Simplify from ~800 lines to ~50 — iterate clips, call `compose.render_clip()` |
| `themes/slides.py` | Add optional `dag_template` field per slide type |

### Untouched files

| File | Reason |
|---|---|
| `spot.py` | Cue sheet builder — feeds audio renderer nodes |
| `drone.py` | Synth helpers — used by audio_synth renderer and score tool |
| `audio_fx.py` | Post-FX — used by narrate and future audio renderers |
| `tools/score.py` | Global drone pipeline stays as-is |
| `tools/stitch.py` | Final assembly — receives per-clip audio from DAG alongside video |
| `tools/narrate.py` | TTS pipeline unchanged |
| `tools/title.py` | Title script builder — called by `_choreo_title` |
| `config.py` | Configuration loading unchanged |
| `split.py` | Clip splitting unchanged |
| `align.py` | Whisper alignment unchanged |
| `direct.py` | Creative direction unchanged |
| `server.py` | MCP tool definitions unchanged (render tool still calls render_all) |

### Deleted code (migrated)

| Code | Lines | Destination |
|---|---|---|
| `_build_data_text_scene` | ~75 | `_choreo_data_text` |
| `_build_counter_sync_scene` | ~62 | `_choreo_counter` |
| `_build_photo_organism_scene` | ~88 | `_choreo_organism_reveal` |
| `_build_chapter_card_scene` | ~32 | `_choreo_chapter_card` (already equivalent) |
| `_build_ambient_field_scene` | ~14 | `_choreo_ambient_field` (new, trivial) |
| `_build_title_scene` | ~40 | `_choreo_title` |
| `build_scene()` in base.py | ~90 | `compose.py` orchestrator |
| Bridge conversion in base.py | ~33 | Gone — DAG speaks native format |
| Legacy wrappers in base.py | ~40 | Gone — no callers |

---

## Build Sequence

1. **compose.py** — orchestrator with DAG walker, topo sort, caching, fusion detection, renderer dispatch
2. **renderers/** — all day-one renderer modules implementing the interface
3. **themes/base.py** — new interface replacing old monolith
4. **themes/biopunk.py** — remove bespoke builders, rewrite choreo methods, add `default_dag()`
5. **tools/render.py** — simplify to orchestrator calls
6. **themes/slides.py** — add `dag_template` field
7. **Tests** — update existing tests, add compose/renderer tests
8. **Validation** — render all 82 yeast clips, verify theme visuals present on every clip

---

## Success Criteria

- All 82 parse-evols-yeast clips render with full biopunk theme visuals (hex grid, imperial border, particles)
- Word-level sync preserved on counter_sync and data_text clips
- HUD border + cue-synced pointer labels preserved on photo_organism clips
- Node-level caching works — changing one node re-renders only that node + downstream
- Manually replacing a node output is picked up by compositor without full re-render
- Adding a new renderer requires only one new file in `renderers/`
- All existing tests pass (adapted for new interfaces)
- No changes to upstream pipeline (plan, split, narrate, align, direct, spot)
- No changes to downstream pipeline (score, stitch)
