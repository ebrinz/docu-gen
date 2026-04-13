# Animation Primitives Design

> Structured animation vocabulary for the `custom_animation` visual type.
> Themes implement each primitive with their own aesthetic.

---

## Problem

The `direction` field in clips.json is free text that the renderer ignores. Custom animations require hand-written Manim scripts per clip, which breaks the clip pipeline and can't be themed.

## Solution

Define a set of **animation primitives** — callable patterns that the theme's `custom_animation` method dispatches on. The `direction` field uses a simple function-call syntax that maps to theme methods.

---

## Direction Syntax

```
primitive_name(param1=value1, param2=value2)
```

Values are strings (unquoted), numbers, or lists (bracket-delimited). The parser is simple string splitting, not a full expression evaluator.

Examples:
```
counter(from=0, to=64659, color=gold)
anchor_drop(name=Ginsenoside Rb1, count=226, color=gold)
dot_merge(dot1=Resveratrol, dot2=PI-103, pathways=[Sir2,TOR], result=+16.4%)
```

---

## Primitives

### 1. `counter`

Animated number tick-up with final hold.

```
counter(from=0, to=64659, color=gold, label=compounds)
```

| Param | Type | Description |
|-------|------|-------------|
| from | int | Start value (default 0) |
| to | int | End value |
| color | string | Palette key (gold, glow, cyan, etc.) |
| label | string | Text below the number (optional) |

**Manim behavior:** Large number in center, counts up with `rush_into` rate function over 3s. Label fades in below. Themed background throughout.

### 2. `fingerprint_compare`

Two radial fingerprint grids side by side with Tanimoto score.

```
fingerprint_compare(mol1=Resveratrol, mol2=Pterostilbene, score=0.89)
```

| Param | Type | Description |
|-------|------|-------------|
| mol1 | string | Left molecule name |
| mol2 | string | Right molecule name |
| score | float | Tanimoto coefficient |

**Manim behavior:** Two rings of small squares (64 each, representing fingerprint bits). Matching bits pulse gold. Venn diagram forms between them. Score appears in the intersection. Hold for duration.

### 3. `sonar_ring`

Expanding ring from a labeled center, dots change color by confidence tier.

```
sonar_ring(center=Rapamycin, high=12, med=45, low=89)
```

| Param | Type | Description |
|-------|------|-------------|
| center | string | Anchor compound name |
| high | int | Number of HIGH confidence hits |
| med | int | Number of MEDIUM hits |
| low | int | Number of LOW hits |

**Manim behavior:** Field of dim dots. Center dot pulses gold with label. Ring expands outward. Dots inside change color in tiers: gold (HIGH), cyan (MED), purple (LOW). Counters appear per tier.

### 4. `anchor_drop`

Single anchor appearing and illuminating nearby compounds.

```
anchor_drop(name=Ginsenoside Rb1, count=226, color=gold)
```

| Param | Type | Description |
|-------|------|-------------|
| name | string | Compound name |
| count | int | Number of compounds illuminated |
| color | string | Palette key |

**Manim behavior:** Dark field. Gold flash at center. Label fades in. Sonar ring expands. Counter ticks up to `count`. Dots in the field light up as the ring passes them.

### 5. `dot_field`

Particle field showing illumination state.

```
dot_field(total=64659, lit_pct=31, label=31% illuminated)
```

| Param | Type | Description |
|-------|------|-------------|
| total | int | Total dots (representative, actual rendered ~300-500) |
| lit_pct | int | Percentage that are illuminated |
| label | string | Text overlay |

**Manim behavior:** Field of dots. `lit_pct`% are colored (gold/cyan/purple tiers). Rest are dim grey. Label fades in. Dots drift slowly for ambient motion.

### 6. `remove_reveal`

Remove a known compound, then reveal its replacement emerging from bulk.

```
remove_reveal(removed=Rapamycin, emerged=PI-103, via=Everolimus, effect=+10.3%)
```

| Param | Type | Description |
|-------|------|-------------|
| removed | string | Compound being removed |
| emerged | string | Proxy that emerges |
| via | string | Anchor that provided the similarity link |
| effect | string | Predicted effect |

**Manim behavior:** Glowing dot labeled `removed`. Red cross appears, dot fades. Beat (2s silence). New dot lights up elsewhere labeled `emerged`. Dotted line drawn to `via` anchor. Effect number appears.

### 7. `dot_merge`

Two compounds approaching, pathway labels, merge with combined effect.

```
dot_merge(dot1=Resveratrol, dot2=PI-103, pathways=[Sir2,TOR], result=+16.4%)
```

| Param | Type | Description |
|-------|------|-------------|
| dot1 | string | First compound |
| dot2 | string | Second compound |
| pathways | list | Pathway labels for each |
| result | string | Combined effect |

**Manim behavior:** Two dots on opposite sides. Labels and pathway tags appear. Dots move toward center. Flash on contact. Combined effect appears large. Hold.

### 8. `bar_chart`

Horizontal bars appearing sequentially.

```
bar_chart(items=[Herbal:22000:glow, Marine:18000:cyan, Pharma:18000:gold, Nutra:900:purple])
```

| Param | Type | Description |
|-------|------|-------------|
| items | list | Colon-delimited label:value:color entries |

**Manim behavior:** Each bar grows from left, label on the left, value on the right. Bars appear sequentially with stagger timing. Themed background.

### 9. `before_after`

Side-by-side counter morph showing improvement.

```
before_after(label=HIGH confidence, before=366, after=763, color=gold)
```

| Param | Type | Description |
|-------|------|-------------|
| label | string | What's being measured |
| before | int/string | Before value |
| after | int/string | After value |
| color | string | Palette key |

**Manim behavior:** "BEFORE" and "AFTER" columns. Before value appears. Arrow or transition. After value morphs in. Delta shown.

### 10. `organism_reveal`

Photo with compound overlay and pathway callout.

```
organism_reveal(image=img_sponge_aplysina.jpg, name=Aplysina aerophoba, compound=Aerothionin, note=Neuroprotection 600Mya)
```

| Param | Type | Description |
|-------|------|-------------|
| image | string | Image filename |
| name | string | Organism name |
| compound | string | Key compound |
| note | string | One-line significance |

**Manim behavior:** Photo fades in on left (Ken Burns zoom). Right side: organism name in accent color, compound in gold, note in dim text. Themed background visible around the photo.

---

## Theme Integration

### ThemeBase additions

```python
class ThemeBase(ABC):
    # ... existing methods ...

    def anim_counter(self, from_val, to_val, color, label, duration) -> str: ...
    def anim_fingerprint_compare(self, mol1, mol2, score, duration) -> str: ...
    def anim_sonar_ring(self, center, high, med, low, duration) -> str: ...
    def anim_anchor_drop(self, name, count, color, duration) -> str: ...
    def anim_dot_field(self, total, lit_pct, label, duration) -> str: ...
    def anim_remove_reveal(self, removed, emerged, via, effect, duration) -> str: ...
    def anim_dot_merge(self, dot1, dot2, pathways, result, duration) -> str: ...
    def anim_bar_chart(self, items, duration) -> str: ...
    def anim_before_after(self, label, before, after, color, duration) -> str: ...
    def anim_organism_reveal(self, image, name, compound, note, duration, images_dir) -> str: ...
```

All return Manim script strings. All include the theme's background elements.

### Direction parser

Add to `src/docugen/tools/render.py`:

```python
def _parse_direction(direction: str) -> tuple[str, dict]:
    """Parse 'primitive_name(k=v, k=v)' into (name, params_dict)."""
```

The `build_clip_script` function checks if `visuals.type == "animation"`, parses the direction, and calls the corresponding `anim_*` method on the theme.

### Fallback

If the direction doesn't match any primitive, fall back to `idle_scene` with the direction text displayed as a subtitle. This means old-format direction strings don't break — they just show as text on a themed background.

---

## Updated clips.json for parse-evols-yeast

After building primitives, update the split output (or manually edit clips.json) to assign animation directions to methodology clips:

- ch2 fingerprint explanation → `fingerprint_compare`
- ch2 confidence tiers → `sonar_ring`
- ch3 source breakdown → `bar_chart`
- ch3 total count → `counter`
- ch4 anchor drops → `anchor_drop` (one per anchor)
- ch4 coverage change → `before_after`
- ch5 dark matter → `dot_field`
- ch6 holdout → `remove_reveal`
- ch7 synergy pairs → `dot_merge`
- ch8 organism photos → `organism_reveal`
- intro particle field → `dot_field` + `counter`
- outro stats → `counter` sequence

---

## Out of Scope

- Physics simulations (particle forces, spring dynamics)
- 3D rendering (stay in 2D Manim)
- Direction field auto-generation from narration text (manual assignment)
- Parameterized timing within primitives (duration comes from clip WAV + pacing)
