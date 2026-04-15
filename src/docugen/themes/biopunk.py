"""Biopunk Imperial visual theme — full implementation."""

import numpy as np

from docugen.themes.base import ThemeBase

palette = {
    "bg": "#050510", "panel": "#0a0e1a", "glow": "#b8ffc4", "glow_dim": "#4a7a52",
    "purple": "#8b5cf6", "purple_deep": "#5b21b6", "purple_faint": "#3b1a6e",
    "sith_red": "#dc2626", "sith_red_dim": "#7f1d1d", "cyan": "#22d3ee",
    "gold": "#f59e0b", "text": "#e2e8f0", "text_dim": "#64748b", "grid": "#1a1a2e",
}
font = "Courier"


# ── Score helpers (local copies so theme is self-contained) ────────────────

_SR = 44100
_D2 = 73.42
_D3 = 146.83
_A2 = 110.0
_F3 = 174.61
_A3 = 220.0
_D4 = 293.66
_F4 = 349.23
_E4 = 329.63


def _sine(freq, dur, sr=_SR, phase=0.0):
    t = np.arange(int(dur * sr)) / sr
    return np.sin(2 * np.pi * freq * t + phase)


def _saw(freq, dur, sr=_SR, harmonics=8):
    t = np.arange(int(dur * sr)) / sr
    out = np.zeros_like(t)
    for h in range(1, harmonics + 1):
        out += ((-1) ** (h + 1)) * np.sin(2 * np.pi * freq * h * t) / h
    return out * 0.5


def _pink_noise(n, rng):
    rows = 16
    arr = rng.standard_normal((rows, n))
    for i in range(1, rows):
        step = 2 ** i
        vals = rng.standard_normal((n + step - 1) // step)
        arr[i, :] = np.repeat(vals, step)[:n]
    out = arr.sum(axis=0)
    out /= np.max(np.abs(out)) + 1e-10
    return out


def _lowpass(sig, cutoff, sr=_SR, order=4):
    from scipy.signal import butter, sosfilt
    sos = butter(order, cutoff, btype="low", fs=sr, output="sos")
    return sosfilt(sos, sig)


def _bandpass(sig, low, high, sr=_SR, order=4):
    from scipy.signal import butter, sosfilt
    sos = butter(order, [low, high], btype="band", fs=sr, output="sos")
    return sosfilt(sos, sig)


def _envelope(n, attack_s=0.0, decay_s=0.0, sustain_frac=1.0, sr=_SR):
    env = np.ones(n) * sustain_frac
    a = min(int(attack_s * sr), n)
    d = min(int(decay_s * sr), n)
    if a > 0:
        env[:a] = np.linspace(0, 1, a) ** 2
    if d > 0:
        env[-d:] = np.linspace(sustain_frac, 0, d) ** 2
    return env


def _reverb(sig, rt60=1.5, wet=0.3, sr=_SR, rng=None):
    from scipy.signal import fftconvolve
    if rng is None:
        rng = np.random.default_rng(0)
    ir_n = int(rt60 * 2 * sr)
    ir = rng.standard_normal(ir_n) * np.exp(-3.0 * np.arange(ir_n) / (rt60 * sr))
    wet_sig = fftconvolve(sig, ir, mode="full")[:len(sig)]
    return (1 - wet) * sig + wet * wet_sig


def _overlay(base, layer, start, amp=1.0):
    end = min(start + len(layer), len(base))
    if start < len(base):
        base[start:end] += layer[:end - start] * amp
    return base


# ── Transition sounds ──────────────────────────────────────────────────────

def transition_imperial_chime(sr=_SR):
    dur = 2.0
    n = int(dur * sr)
    t = np.arange(n) / sr
    sig = 0.5 * np.sin(2 * np.pi * _A3 * t)
    sig += 0.3 * np.sin(2 * np.pi * 554.37 * t)
    sig += 0.2 * np.sin(2 * np.pi * 880 * t)
    sig += 0.15 * np.sin(2 * np.pi * 1108.73 * t)
    sig *= _envelope(n, attack_s=0.005, decay_s=1.8)
    return sig


def transition_dark_swell(sr=_SR):
    dur = 3.0
    n = int(dur * sr)
    rng = np.random.default_rng(77)
    sub = _sine(_D2 * 0.5, dur)
    sub *= _envelope(n, attack_s=1.5, decay_s=1.2)
    noise = _pink_noise(n, rng)
    noise = _lowpass(noise, 200)
    noise *= _envelope(n, attack_s=2.0, decay_s=0.8) * 0.3
    return sub * 0.6 + noise


def transition_crystal_ping(sr=_SR):
    dur = 1.5
    n = int(dur * sr)
    t = np.arange(n) / sr
    sig = np.sin(2 * np.pi * _D4 * 2 * t)
    sig += 0.5 * np.sin(2 * np.pi * _A3 * 4 * t)
    sig *= _envelope(n, attack_s=0.002, decay_s=1.3)
    sig *= 0.4
    return sig


def transition_heartbeat(sr=_SR):
    dur = 2.0
    n = int(dur * sr)
    sig = np.zeros(n)
    for offset in [0.0, 0.3]:
        start = int(offset * sr)
        pulse_n = int(0.15 * sr)
        pulse = _sine(_D2, 0.15) * _envelope(pulse_n, attack_s=0.01, decay_s=0.12)
        _overlay(sig, pulse * 0.7, start)
    return sig


def transition_bell(sr=_SR):
    dur = 4.0
    n = int(dur * sr)
    t = np.arange(n) / sr
    sig = 0.6 * np.sin(2 * np.pi * _D4 * t)
    sig += 0.3 * np.sin(2 * np.pi * _D4 * 2.76 * t)
    sig += 0.15 * np.sin(2 * np.pi * _D4 * 5.4 * t)
    sig *= _envelope(n, attack_s=0.003, decay_s=3.5)
    return sig


def transition_sonar(sr=_SR):
    dur = 2.0
    n = int(dur * sr)
    t = np.arange(n) / sr
    freq = _A3 * np.exp(-t * 2)
    sig = np.sin(2 * np.pi * np.cumsum(freq) / sr)
    sig *= _envelope(n, attack_s=0.01, decay_s=1.5)
    return sig * 0.5


def transition_resolve(sr=_SR):
    dur = 3.0
    n = int(dur * sr)
    d_tone = _sine(_D3, dur) * 0.4
    a_tone = _sine(_A3, dur) * 0.35
    sig = d_tone + a_tone
    sig *= _envelope(n, attack_s=0.5, decay_s=1.0)
    return sig


def transition_tension(sr=_SR):
    dur = 2.5
    n = int(dur * sr)
    d_tone = _sine(_D3, dur) * 0.3
    ab_tone = _sine(_D3 * np.sqrt(2), dur) * 0.25
    sig = d_tone + ab_tone
    sig *= _envelope(n, attack_s=0.3, decay_s=1.5)
    return sig


# ── Chapter drone layers ───────────────────────────────────────────────────

def _layer_intro(n, sr, rng):
    pad = _sine(_D2, n / sr) * 0.3
    pad += _sine(_D3, n / sr) * 0.15
    pad = _lowpass(pad, 300)
    pad = _reverb(pad, rt60=3.0, wet=0.5, rng=rng)
    return pad


def _layer_ch1(n, sr, rng):
    out = np.zeros(n)
    beat_interval = sr
    for i in range(0, n, beat_interval):
        pulse = _sine(_D2, 0.2) * _envelope(int(0.2 * sr), attack_s=0.01, decay_s=0.15)
        _overlay(out, pulse * 0.25, i)
    pad = _sine(_D3, n / sr) * 0.12
    pad += _sine(_A2, n / sr) * 0.08
    pad = _lowpass(pad, 400)
    return out + pad


def _layer_ch2(n, sr, rng):
    out = np.zeros(n)
    notes = [_D4, _F4, _A3, _D4, _E4, _A3]
    note_dur = 0.8
    note_n = int(note_dur * sr)
    gap = int(1.2 * sr)
    pos = 0
    i = 0
    while pos < n:
        freq = notes[i % len(notes)]
        note = _sine(freq, note_dur) * _envelope(note_n, attack_s=0.01, decay_s=0.6) * 0.15
        note = _reverb(note, rt60=2.0, wet=0.6, rng=rng)
        _overlay(out, note, pos)
        pos += gap
        i += 1
    return out


def _layer_ch3(n, sr, rng):
    out = np.zeros(n)
    beat_interval = int(sr * 0.8)
    for i in range(0, n, beat_interval):
        pulse = _sine(_D2, 0.15) * _envelope(int(0.15 * sr), attack_s=0.005, decay_s=0.12)
        _overlay(out, pulse * 0.3, i)
    sub = _sine(_D2 * 0.5, n / sr) * 0.2
    sub *= np.linspace(0.3, 1.0, n)
    sub = _lowpass(sub, 100)
    return out + sub


def _layer_ch4(n, sr, rng):
    out = np.zeros(n)
    chime_interval = int(8 * sr)
    for i in range(0, n, chime_interval):
        chime = transition_bell()[:int(2 * sr)]
        _overlay(out, chime * 0.2, i)
    half = n // 2
    pad_n = n - half
    pad = (_sine(_D3, pad_n / sr) * 0.1 +
           _sine(_F3, pad_n / sr) * 0.08 +
           _sine(_A3, pad_n / sr) * 0.08 +
           _sine(_E4, pad_n / sr) * 0.06)
    pad *= _envelope(pad_n, attack_s=3.0, decay_s=2.0)
    pad = _lowpass(pad, 500)
    _overlay(out, pad, half)
    return out


def _layer_ch5(n, sr, rng):
    drone = _sine(_D2, n / sr) * 0.15
    drone = _lowpass(drone, 200)
    noise = _pink_noise(n, rng) * 0.03
    noise = _lowpass(noise, 150)
    return drone + noise


def _layer_ch6(n, sr, rng):
    pad = _sine(_D3, n / sr) * 0.12
    pad += _sine(_F3, n / sr) * 0.1
    pad += _sine(_A3, n / sr) * 0.08
    pad += _sine(261.63, n / sr) * 0.06
    pad *= _envelope(n, attack_s=4.0, decay_s=2.0)
    pad = _lowpass(pad, 600)
    pad = _reverb(pad, rt60=2.0, wet=0.4, rng=rng)
    return pad


def _layer_ch7(n, sr, rng):
    out = np.zeros(n)
    mel1_notes = [_D4, _F4, _A3, _D4]
    mel2_notes = [_A3, _D4, _F4, _E4]
    note_dur = 1.5
    note_n = int(note_dur * sr)
    gap = int(2.0 * sr)
    pos = 0
    i = 0
    while pos < n:
        n1 = _sine(mel1_notes[i % 4], note_dur) * _envelope(note_n, 0.05, 1.0) * 0.12
        _overlay(out, n1, pos)
        n2 = _sine(mel2_notes[i % 4], note_dur) * _envelope(note_n, 0.05, 1.0) * 0.10
        _overlay(out, n2, pos + int(0.8 * sr))
        pos += gap
        i += 1
    out = _reverb(out, rt60=1.5, wet=0.4, rng=rng)
    return out


def _layer_ch8(n, sr, rng):
    out = np.zeros(n)
    grain_interval = int(0.3 * sr)
    for i in range(0, n, grain_interval):
        grain_len = int(np.random.uniform(0.05, 0.15) * sr)
        grain = rng.standard_normal(grain_len)
        grain = _bandpass(grain, 200, 2000)
        grain *= _envelope(grain_len, attack_s=0.01, decay_s=0.08) * 0.06
        _overlay(out, grain, i)
    pad = _sine(_D3, n / sr) * 0.1 + _sine(_A2, n / sr) * 0.08
    pad = _lowpass(pad, 400)
    return out + pad


def _layer_ch9(n, sr, rng):
    pad = _sine(_D3, n / sr) * 0.12
    pad += _sine(_F3, n / sr) * 0.08
    pad += _sine(_A3, n / sr) * 0.08
    pad += _sine(_D4, n / sr) * 0.06
    pad *= np.linspace(0.5, 1.0, n)
    resolve_start = n - int(5.0 * sr)
    if resolve_start > 0:
        resolve = _sine(_D3, 5.0) * 0.15 + _sine(_A3, 5.0) * 0.12
        resolve *= _envelope(int(5 * sr), attack_s=1.0, decay_s=2.0)
        _overlay(pad, resolve, resolve_start)
    pad = _reverb(pad, rt60=2.0, wet=0.45, rng=rng)
    return pad


def _layer_outro(n, sr, rng):
    drone = _sine(_D2, n / sr) * 0.2
    drone *= np.linspace(1.0, 0.0, n)
    drone = _lowpass(drone, 200)
    bell_start = n - int(4.0 * sr)
    if bell_start > 0:
        bell = transition_bell()
        _overlay(drone, bell * 0.35, bell_start)
    return drone


# ── Theme class ────────────────────────────────────────────────────────────

class BiopunkTheme(ThemeBase):
    name = "biopunk"
    palette = palette
    font = font

    def manim_header(self) -> str:
        p = self.palette
        return (
            f'from manim import *\n'
            f'import numpy as np\n'
            f'\n'
            f'# ── Biopunk Imperial Theme ──\n'
            f'BG = "{p["bg"]}"\n'
            f'GLOW = "{p["glow"]}"\n'
            f'GLOW_DIM = "{p["glow_dim"]}"\n'
            f'PURPLE = "{p["purple"]}"\n'
            f'PURPLE_DEEP = "{p["purple_deep"]}"\n'
            f'PURPLE_FAINT = "{p["purple_faint"]}"\n'
            f'SITH_RED = "{p["sith_red"]}"\n'
            f'SITH_RED_DIM = "{p["sith_red_dim"]}"\n'
            f'CYAN = "{p["cyan"]}"\n'
            f'GOLD = "{p["gold"]}"\n'
            f'TEXT_COL = "{p["text"]}"\n'
            f'TEXT_DIM = "{p["text_dim"]}"\n'
            f'GRID_COL = "{p["grid"]}"\n'
            f'PANEL_COL = "{p["panel"]}"\n'
            f'\n'
            f'config.background_color = BG\n'
            + r'''
def throb_title(scene, mob, cycles=3, scale_factor=1.04, cycle_time=1.2):
    """Pulsing glow effect on a text mobject."""
    for _ in range(cycles):
        scene.play(
            mob.animate.scale(scale_factor).set_opacity(1.0),
            run_time=cycle_time / 2, rate_func=smooth,
        )
        scene.play(
            mob.animate.scale(1 / scale_factor).set_opacity(0.85),
            run_time=cycle_time / 2, rate_func=smooth,
        )


def make_hex_grid(rows=8, cols=12, radius=0.3, color=GRID_COL, opacity=0.15):
    """Create an Imperial-style hexagonal grid background."""
    hexes = VGroup()
    for r in range(rows):
        for c in range(cols):
            x = c * radius * 1.75 + (r % 2) * radius * 0.875
            y = r * radius * 1.52
            h = RegularPolygon(n=6, radius=radius, color=color,
                               stroke_width=0.5, fill_opacity=0)
            h.set_opacity(opacity)
            h.move_to(np.array([x - cols * radius * 0.875, y - rows * radius * 0.76, 0]))
            hexes.add(h)
    return hexes


def scanline(scene, duration=2.0, color=PURPLE):
    """Horizontal scanline sweep — Imperial scanner aesthetic."""
    line = Line(LEFT * 8, RIGHT * 8, color=color, stroke_width=1.5, stroke_opacity=0.6)
    line.move_to(UP * 4.5)
    scene.play(line.animate.move_to(DOWN * 4.5), run_time=duration, rate_func=linear)
    scene.remove(line)


def make_particle_field(n=200, spread=7.0, color=GLOW, min_size=0.01, max_size=0.04):
    """Floating particle field — bioluminescent spores."""
    dots = VGroup()
    for _ in range(n):
        x = np.random.uniform(-spread, spread)
        y = np.random.uniform(-spread * 0.6, spread * 0.6)
        r = np.random.uniform(min_size, max_size)
        d = Dot(point=[x, y, 0], radius=r, color=color)
        d.set_opacity(np.random.uniform(0.1, 0.5))
        dots.add(d)
    return dots


def imperial_border(width=13.0, height=7.5, color=SITH_RED_DIM):
    """Angled corner brackets — Imperial HUD frame."""
    hw, hh = width / 2, height / 2
    corner_len = 0.8
    lines = VGroup()
    for sx, sy in [(-1,-1), (-1,1), (1,-1), (1,1)]:
        cx, cy = sx * hw, sy * hh
        h_line = Line([cx, cy, 0], [cx - sx * corner_len, cy, 0],
                       color=color, stroke_width=2)
        v_line = Line([cx, cy, 0], [cx, cy - sy * corner_len, 0],
                       color=color, stroke_width=2)
        lines.add(h_line, v_line)
    return lines


def make_dna_helix(height=6.0, n_points=60, color1=GLOW, color2=PURPLE):
    """Vertical double helix — biopunk DNA strand."""
    strand1_pts = []
    strand2_pts = []
    for i in range(n_points):
        t = i / n_points * 4 * PI
        y = -height/2 + (i / n_points) * height
        strand1_pts.append([0.8 * np.cos(t), y, 0])
        strand2_pts.append([0.8 * np.cos(t + PI), y, 0])
    s1 = VMobject(color=color1, stroke_width=2, stroke_opacity=0.6)
    s1.set_points_smoothly([np.array(p) for p in strand1_pts])
    s2 = VMobject(color=color2, stroke_width=2, stroke_opacity=0.6)
    s2.set_points_smoothly([np.array(p) for p in strand2_pts])
    rungs = VGroup()
    for i in range(0, n_points, 4):
        if i < len(strand1_pts) and i < len(strand2_pts):
            rung = Line(strand1_pts[i], strand2_pts[i],
                       color=GLOW_DIM, stroke_width=1, stroke_opacity=0.3)
            rungs.add(rung)
    return VGroup(s1, s2, rungs)


def alive_wait(scene, duration, particles=None, extras=None):
    """Replace dead self.wait() with living motion."""
    if duration <= 0:
        return

    anims = []

    if particles is not None:
        dx = np.random.uniform(-0.15, 0.15)
        dy = np.random.uniform(-0.08, 0.08)
        anims.append(particles.animate.shift(np.array([dx, dy, 0])))

    if extras:
        for mob in extras:
            if np.random.random() > 0.5:
                anims.append(mob.animate.scale(1.01 + np.random.uniform(0, 0.02)))
            else:
                anims.append(mob.animate.shift(np.array([
                    np.random.uniform(-0.02, 0.02),
                    np.random.uniform(-0.02, 0.02), 0])))

    if anims:
        scene.play(*anims, run_time=duration, rate_func=linear)
    else:
        if duration > 3:
            line = Line(LEFT * 8, RIGHT * 8, color=PURPLE_FAINT,
                       stroke_width=0.5, stroke_opacity=0.3)
            line.move_to(UP * 4)
            scene.play(line.animate.move_to(DOWN * 4),
                      run_time=duration, rate_func=linear)
            scene.remove(line)
        else:
            scene.wait(duration)


def pulse_ring(scene, center=ORIGIN, color=GLOW, duration=2.0):
    """Emit a sonar-like expanding ring from a point."""
    ring = Circle(radius=0.1, color=color, stroke_width=1.5, stroke_opacity=0.6)
    ring.move_to(center)
    scene.play(ring.animate.scale(25).set_opacity(0),
               run_time=duration, rate_func=linear)
    scene.remove(ring)


def breathing(mob, scene, duration=3.0, scale=1.02):
    """Gentle scale oscillation on a mobject."""
    cycles = max(int(duration / 1.5), 1)
    for _ in range(cycles):
        t = duration / (cycles * 2)
        scene.play(mob.animate.scale(scale), run_time=t, rate_func=smooth)
        scene.play(mob.animate.scale(1/scale), run_time=t, rate_func=smooth)


def make_floating_bg(n=80, spread=7.0):
    """Background dots that drift when animated — use with alive_wait."""
    dots = VGroup()
    for _ in range(n):
        x = np.random.uniform(-spread, spread)
        y = np.random.uniform(-spread * 0.6, spread * 0.6)
        r = np.random.uniform(0.008, 0.025)
        color = [GLOW, PURPLE, CYAN][np.random.randint(0, 3)]
        d = Dot(point=[x, y, 0], radius=r, color=color)
        d.set_opacity(np.random.uniform(0.05, 0.2))
        dots.add(d)
    return dots
'''
        )

    # ── Three-Layer Rendering ─────────────────────────────────

    def render_theme_layer(self, elements: list[str]) -> str:
        """Return Manim code for background elements."""
        lines = []
        if "hex_grid" in elements:
            lines.append("        grid = make_hex_grid(rows=10, cols=16, radius=0.35)")
            lines.append("        self.add(grid)")
        if "particle_field" in elements:
            lines.append("        particles = make_particle_field(n=300, color=GLOW)")
            lines.append("        self.add(particles)")
        if "dna_helix" in elements:
            lines.append("        dna_left = make_dna_helix().shift(LEFT * 6).set_opacity(0.3)")
            lines.append("        dna_right = make_dna_helix().shift(RIGHT * 6).set_opacity(0.3)")
            lines.append("        self.add(dna_left, dna_right)")
        if "floating_bg" in elements:
            lines.append("        bg = make_floating_bg()")
            lines.append("        self.add(bg)")
        if "imperial_border" in elements:
            lines.append("        border = imperial_border()")
            lines.append("        self.play(Create(border), run_time=1.0)")
        return "\n".join(lines) if lines else "        pass  # no theme elements"

    def render_content_layer(self, assets: list[str], placement: str,
                             images_dir: str) -> str:
        """Return Manim code that places content assets."""
        if not assets:
            return ""

        lines = []
        for i, asset in enumerate(assets):
            path = f"{images_dir}/{asset}".replace("\\", "\\\\")
            var = f"asset_{i}"

            # Position based on placement
            if placement == "left":
                pos = "LEFT * 2.5"
            elif placement == "right":
                pos = "RIGHT * 2.5"
            else:
                pos = "ORIGIN"

            if asset.lower().endswith(".svg"):
                lines.append(f"        try:")
                lines.append(f"            {var} = SVGMobject(\"{path}\").scale(2.5)")
                lines.append(f"            {var}.move_to({pos})")
                lines.append(f"            self.play(FadeIn({var}), run_time=1.5)")
                lines.append(f"        except Exception:")
                lines.append(f"            {var} = Dot(ORIGIN, radius=0.01).set_opacity(0)")
            else:
                lines.append(f"        try:")
                lines.append(f"            {var} = ImageMobject(\"{path}\")")
                lines.append(f"            {var}.height = 4.5")
                lines.append(f"            {var}.width = min({var}.width * (4.5 / {var}.height), 5.5)")
                lines.append(f"            {var}.move_to({pos})")
                lines.append(f"            self.play(FadeIn({var}), run_time=1.5)")
                lines.append(f"            self.play({var}.animate.scale(1.04), run_time=3.0, rate_func=linear)")
                lines.append(f"        except Exception:")
                lines.append(f"            {var} = Dot(ORIGIN, radius=0.01).set_opacity(0)")

        return "\n".join(lines)

    # Post-processing filters by slide type — tasteful, not overwhelming
    _POST_FILTERS = {
        "title": ["vignette"],             # dramatic framing for opening
        "chapter_card": ["vignette"],       # frame the transition
        "ambient_field": ["vignette"],      # moody breathing room
        "photo_organism": ["sharpen"],      # make the photo pop
    }

    def default_dag(self, clip: dict) -> list[dict]:
        visuals = clip.get("visuals", {})
        slide_type = visuals.get("slide_type", "")
        assets = visuals.get("assets", [])
        cue_words = visuals.get("cue_words", [])

        nodes = [
            {"name": "bg", "renderer": "manim_theme",
             "elements": ["hex_grid", "imperial_border", "floating_bg"]},
        ]

        if assets:
            nodes.append({
                "name": "content", "renderer": "static_asset",
                "asset": assets[0],
                "layout": visuals.get("layout", "center"),
            })
            nodes.append({
                "name": "choreo", "renderer": "manim_choreo",
                "refs": ["bg", "content"],
            })
            fused_inputs = "bg+content+choreo"
        else:
            nodes.append({
                "name": "choreo", "renderer": "manim_choreo",
                "refs": ["bg"],
            })
            fused_inputs = "bg+choreo"

        # Audio cues node — generates synth sounds keyed to cue events
        if cue_words:
            nodes.append({
                "name": "audio_cues", "renderer": "audio_synth",
            })

        nodes.append({
            "name": "composite", "renderer": "ffmpeg_composite",
            "inputs": [fused_inputs],
        })

        # Post-processing — slide-type-specific filters
        filters = self._POST_FILTERS.get(slide_type, [])
        audio_inputs = ["audio_cues"] if cue_words else []
        nodes.append({
            "name": "post", "renderer": "ffmpeg_post",
            "inputs": ["composite"],
            "filters": filters,
            "audio": audio_inputs,
        })

        return nodes

    def render_choreography(self, clip: dict, duration: float,
                            images_dir: str) -> str:
        """Return Manim code for animation choreography."""
        visuals = clip.get("visuals", {})
        slide_type = visuals.get("slide_type", "")

        method_map = {
            "chapter_card": self._choreo_chapter_card,
            "counter_sync": self._choreo_counter,
            "data_text": self._choreo_data_text,
            "photo_organism": self._choreo_organism_reveal,
            "bar_chart_build": self._choreo_bar_chart,
            "before_after": self._choreo_before_after,
            "dot_merge": self._choreo_dot_merge,
            "remove_reveal": self._choreo_remove_reveal,
            "svg_reveal": self._choreo_svg_reveal,
            "ambient_field": self._choreo_ambient_field,
            "title": self._choreo_title,
            "fingerprint_compare": self._choreo_fingerprint_compare,
            "sonar_ring": self._choreo_sonar_ring,
            "anchor_drop": self._choreo_anchor_drop,
            "dot_field": self._choreo_dot_field,
        }

        method = method_map.get(slide_type)
        if method:
            return method(clip, duration, images_dir)
        return ""

    # ── Choreography Primitives (return indented code blocks) ──

    def _choreo_chapter_card(self, clip, duration, images_dir):
        visuals = clip.get("visuals", {})
        cue_words = visuals.get("cue_words", [])
        params = {}
        for cue in cue_words:
            params.update(cue.get("params", {}))
        num = params.get("num", "00")
        title = params.get("title", "UNTITLED")
        return f'''        # Chapter card
        ch_num = Text("{num}", font="Courier", color=SITH_RED, weight=BOLD).scale(1.5)
        ch_title = Text("{title}", font="Courier", color=GLOW, weight=BOLD).scale(0.9)
        ch_title.next_to(ch_num, RIGHT, buff=0.4)
        card = VGroup(ch_num, ch_title).move_to(ORIGIN)
        self.play(FadeIn(card, shift=RIGHT * 0.3), run_time=1.0)
        throb_title(self, ch_title, cycles=2, scale_factor=1.03, cycle_time=1.0)
        alive_wait(self, {max(duration - 4.0, 0.5):.1f}, particles=bg)'''

    def _choreo_counter(self, clip, duration, images_dir):
        visuals = clip.get("visuals", {})
        cue_words = visuals.get("cue_words", [])
        word_times = clip.get("word_times", [])
        count_time = 0.5
        count_to = 0
        count_color = palette["gold"]
        count_label = ""
        for cue in cue_words:
            if cue.get("event") == "start_count":
                idx = cue.get("at_index", 0)
                if idx < len(word_times):
                    count_time = word_times[idx]["start"]
                params = cue.get("params", {})
                count_to = params.get("to", 0)
                color_name = params.get("color", "gold")
                color_map = {"gold": palette["gold"], "cyan": palette["cyan"],
                             "green": palette["glow"], "red": palette["sith_red"]}
                count_color = color_map.get(color_name, palette["gold"])
                count_label = params.get("label", "")
                break
        try:
            count_val = int(str(count_to).replace(",", ""))
        except (ValueError, TypeError):
            count_val = 0
        label_code = ""
        if count_label:
            label_code = f'\n        lbl = Text("{count_label}", color=TEXT_DIM, font_size=36)\n        lbl.next_to(counter, DOWN, buff=0.5)\n        self.play(FadeIn(lbl), run_time=0.5)'
        return f'''        # Counter sync: wait for cue at {count_time:.2f}s, count to {count_val}
        if {count_time} > 0.05:
            self.wait({count_time})
        counter = Text("{count_val:,}", color="{count_color}", font_size=144, weight=BOLD)
        counter.set_opacity(0)
        self.add(counter)
{label_code}
        count_dur = min(2.5, {duration} - {count_time} - 1.5)
        self.play(counter.animate.set_opacity(1.0), run_time=max(count_dur, 0.5), rate_func=rush_from)
        self.play(counter.animate.scale(1.08), run_time=0.15)
        self.play(counter.animate.scale(1/1.08), run_time=0.3)
        hold = max({duration} - {count_time} - count_dur - 1.5, 0.3)
        alive_wait(self, hold, particles=bg)'''

    def _choreo_fingerprint_compare(self, clip, duration, images_dir):
        visuals = clip.get("visuals", {})
        cue_words = visuals.get("cue_words", [])
        params = {}
        for cue in cue_words:
            params.update(cue.get("params", {}))
        mol1 = params.get("mol1", "A")
        mol2 = params.get("mol2", "B")
        score = float(params.get("score", 0))
        return f'''        # Fingerprint: {mol1} vs {mol2}
        l_label = Text("{mol1}", font="Courier", color=GOLD, weight=BOLD).scale(0.5)
        r_label = Text("{mol2}", font="Courier", color=CYAN, weight=BOLD).scale(0.5)
        l_label.move_to(LEFT * 3.5 + UP * 2.5)
        r_label.move_to(RIGHT * 3.5 + UP * 2.5)
        self.play(FadeIn(l_label), FadeIn(r_label), run_time=0.8)
        l_ring = VGroup()
        r_ring = VGroup()
        for i in range(48):
            angle = i / 48 * TAU
            pos_l = LEFT * 3.5 + np.array([1.8*np.cos(angle), 1.8*np.sin(angle), 0])
            pos_r = RIGHT * 3.5 + np.array([1.8*np.cos(angle), 1.8*np.sin(angle), 0])
            match = np.random.random() < {score}
            col = GOLD if match else GRID_COL
            l_ring.add(Square(side_length=0.12, color=col, fill_opacity=0.8 if match else 0.2).move_to(pos_l))
            r_ring.add(Square(side_length=0.12, color=col, fill_opacity=0.8 if match else 0.2).move_to(pos_r))
        self.play(FadeIn(l_ring, lag_ratio=0.02), FadeIn(r_ring, lag_ratio=0.02), run_time=2.0)
        score_text = Text("Tanimoto: {score:.2f}", font="Courier", color=GLOW, weight=BOLD).scale(0.6)
        score_text.move_to(DOWN * 1.5)
        self.play(FadeIn(score_text, scale=1.3), run_time=1.0)
        alive_wait(self, {max(duration - 6.0, 1.0):.1f}, particles=bg)'''

    def _choreo_sonar_ring(self, clip, duration, images_dir):
        visuals = clip.get("visuals", {})
        cue_words = visuals.get("cue_words", [])
        params = {}
        for cue in cue_words:
            params.update(cue.get("params", {}))
        center = params.get("center", "Anchor")
        high = int(params.get("high", 0))
        med = int(params.get("med", 0))
        low = int(params.get("low", 0))
        return f'''        # Sonar ring: {center}
        field = VGroup()
        for _ in range(200):
            x, y = np.random.uniform(-5.5, 5.5), np.random.uniform(-3, 3)
            field.add(Dot([x,y,0], radius=0.025, color=TEXT_DIM).set_opacity(0.12))
        self.add(field)
        anchor = Dot(ORIGIN, radius=0.15, color=GOLD).set_opacity(0.9)
        anchor_label = Text("{center}", font="Courier", color=GOLD, weight=BOLD).scale(0.35)
        anchor_label.next_to(anchor, DOWN, buff=0.2)
        self.play(FadeIn(anchor, scale=2.0), FadeIn(anchor_label), run_time=1.0)
        ring = Circle(radius=0.2, color=GOLD, stroke_width=2, stroke_opacity=0.8)
        self.play(ring.animate.scale(30).set_opacity(0), run_time=3.0, rate_func=linear)
        self.remove(ring)
        tiers = VGroup(
            Text("HIGH: {high}", font="Courier", color=GOLD, weight=BOLD).scale(0.4),
            Text("MED:  {med}", font="Courier", color=CYAN).scale(0.4),
            Text("LOW:  {low}", font="Courier", color=PURPLE).scale(0.4),
        ).arrange(DOWN, buff=0.2, aligned_edge=LEFT).to_corner(DR, buff=0.8)
        self.play(FadeIn(tiers, lag_ratio=0.3), run_time=1.5)
        alive_wait(self, {max(duration - 7.0, 1.0):.1f}, particles=bg)'''

    def _choreo_anchor_drop(self, clip, duration, images_dir):
        visuals = clip.get("visuals", {})
        cue_words = visuals.get("cue_words", [])
        params = {}
        for cue in cue_words:
            params.update(cue.get("params", {}))
        name = params.get("name", "Compound")
        count = int(params.get("count", 0))
        color = str(params.get("color", "gold")).upper()
        return f'''        # Anchor drop: {name} +{count}
        field = VGroup()
        for _ in range(250):
            x, y = np.random.uniform(-5.5, 5.5), np.random.uniform(-3, 3)
            field.add(Dot([x,y,0], radius=0.02, color=TEXT_DIM).set_opacity(0.1))
        self.add(field)
        flash = Dot(ORIGIN, radius=0.2, color={color}).set_opacity(0.9)
        label = Text("{name}", font="Courier", color={color}, weight=BOLD).scale(0.45)
        label.next_to(flash, DOWN, buff=0.3)
        self.play(FadeIn(flash, scale=3.0), FadeIn(label), run_time=0.8)
        ring = Circle(radius=0.2, color={color}, stroke_width=2)
        self.play(ring.animate.scale(25).set_opacity(0), run_time=2.0, rate_func=linear)
        self.remove(ring)
        counter = Text("+{count}", font="Courier", color={color}, weight=BOLD).scale(0.7)
        counter.next_to(label, DOWN, buff=0.3)
        self.play(FadeIn(counter, scale=1.5), run_time=0.8)
        throb_title(self, counter, cycles=2, scale_factor=1.05, cycle_time=0.8)
        alive_wait(self, {max(duration - 6.0, 1.0):.1f}, particles=bg)'''

    def _choreo_dot_field(self, clip, duration, images_dir):
        visuals = clip.get("visuals", {})
        cue_words = visuals.get("cue_words", [])
        params = {}
        for cue in cue_words:
            params.update(cue.get("params", {}))
        total = int(params.get("total", 64659))
        lit_pct = int(params.get("lit_pct", 31))
        label = params.get("label", "")
        n_dots = min(total // 100, 500)
        n_lit = int(n_dots * lit_pct / 100)
        label_code = ""
        if label:
            label_code = f'''
        lbl = Text("{label}", font="Courier", color=GLOW).scale(0.45)
        lbl.to_edge(DOWN, buff=0.8)
        self.play(FadeIn(lbl, shift=UP * 0.2), run_time=1.0)'''
        return f'''        # Dot field: {lit_pct}% of {total}
        field = VGroup()
        colors = [GOLD, CYAN, PURPLE]
        for i in range({n_dots}):
            x, y = np.random.uniform(-6, 6), np.random.uniform(-3.5, 3.5)
            if i < {n_lit}:
                col = colors[i % 3]
                op = np.random.uniform(0.3, 0.7)
            else:
                col = TEXT_DIM
                op = np.random.uniform(0.05, 0.12)
            field.add(Dot([x,y,0], radius=0.025, color=col).set_opacity(op))
        self.play(FadeIn(field, lag_ratio=0.003), run_time=2.0){label_code}
        alive_wait(self, {max(duration - 4.0, 1.0):.1f}, particles=bg)'''

    def _choreo_remove_reveal(self, clip, duration, images_dir):
        visuals = clip.get("visuals", {})
        cue_words = visuals.get("cue_words", [])
        params = {}
        for cue in cue_words:
            params.update(cue.get("params", {}))
        removed = params.get("removed", "A")
        emerged = params.get("emerged", "B")
        via = params.get("via", "C")
        effect = params.get("effect", "")
        beat = min(duration * 0.12, 2.0)
        effect_code = ""
        if effect:
            effect_code = f'''
        eff = Text("{effect}", font="Courier", color=GOLD, weight=BOLD).scale(0.6)
        eff.next_to(via_text, DOWN, buff=0.3)
        self.play(FadeIn(eff, scale=1.3), run_time=0.8)
        throb_title(self, eff, cycles=1, scale_factor=1.05)'''
        return f'''        # Remove-reveal: {removed} -> {emerged}
        dot1 = Dot(LEFT * 2, radius=0.2, color=GOLD).set_opacity(0.9)
        dot1_label = Text("{removed}", font="Courier", color=GOLD, weight=BOLD).scale(0.4)
        dot1_label.next_to(dot1, DOWN, buff=0.2)
        self.play(FadeIn(dot1, scale=2.0), FadeIn(dot1_label), run_time=1.0)
        alive_wait(self, {beat:.1f}, particles=bg)
        cross = Cross(stroke_color=SITH_RED, stroke_width=6).scale(0.3).move_to(dot1)
        removed_text = Text("REMOVED", font="Courier", color=SITH_RED, weight=BOLD).scale(0.4)
        removed_text.next_to(dot1, UP, buff=0.4)
        self.play(Create(cross), dot1.animate.set_opacity(0.15), FadeIn(removed_text, scale=1.3), run_time=0.8)
        alive_wait(self, {beat:.1f}, particles=bg)
        self.play(FadeOut(cross), FadeOut(removed_text), FadeOut(dot1), FadeOut(dot1_label), run_time=0.5)
        alive_wait(self, {beat:.1f}, particles=bg)
        dot2 = Dot(RIGHT * 2, radius=0.2, color=GLOW).set_opacity(0.9)
        dot2_label = Text("{emerged}", font="Courier", color=GLOW, weight=BOLD).scale(0.45)
        dot2_label.next_to(dot2, DOWN, buff=0.2)
        self.play(FadeIn(dot2, scale=3.0), FadeIn(dot2_label), run_time=1.0)
        via_text = Text("via {via}", font="Courier", color=PURPLE).scale(0.3)
        via_text.next_to(dot2_label, DOWN, buff=0.15)
        self.play(FadeIn(via_text), run_time=0.5){effect_code}
        alive_wait(self, {max(duration - 9.0, 1.0):.1f}, particles=bg)'''

    def _choreo_dot_merge(self, clip, duration, images_dir):
        visuals = clip.get("visuals", {})
        cue_words = visuals.get("cue_words", [])
        params = {}
        for cue in cue_words:
            params.update(cue.get("params", {}))
        d1 = params.get("dot1", "A")
        d2 = params.get("dot2", "B")
        pathways = params.get("pathways", [])
        if isinstance(pathways, str): pathways = [pathways]
        pw = " + ".join(pathways) if pathways else ""
        result = params.get("result", "")
        pw_code = ""
        if pw:
            pw_code = f'''
        pw = Text("{pw}", font="Courier", color=CYAN).scale(0.3)
        pw.move_to(UP * 2)
        self.play(FadeIn(pw), run_time=0.5)'''
        result_code = ""
        if result:
            result_code = f'''
        res = Text("{result}", font="Courier", color=GLOW, weight=BOLD).scale(0.8)
        res.move_to(UP * 0.5)
        self.play(FadeIn(res, scale=1.3), run_time=0.8)
        throb_title(self, res, cycles=2, scale_factor=1.05, cycle_time=0.8)'''
        return f'''        # Dot merge: {d1} + {d2}
        d1 = Dot(LEFT * 4, radius=0.15, color=PURPLE)
        d2 = Dot(RIGHT * 4, radius=0.15, color=GOLD)
        l1 = Text("{d1}", font="Courier", color=PURPLE, weight=BOLD).scale(0.3)
        l2 = Text("{d2}", font="Courier", color=GOLD, weight=BOLD).scale(0.3)
        l1.next_to(d1, DOWN, buff=0.2)
        l2.next_to(d2, DOWN, buff=0.2)
        self.play(FadeIn(d1), FadeIn(d2), FadeIn(l1), FadeIn(l2), run_time=1.0){pw_code}
        self.play(d1.animate.move_to(LEFT * 0.3), d2.animate.move_to(RIGHT * 0.3),
                  l1.animate.move_to(DOWN * 1.5 + LEFT * 2),
                  l2.animate.move_to(DOWN * 1.5 + RIGHT * 2), run_time=2.0)
        flash = Dot(ORIGIN, radius=0.3, color=GLOW).set_opacity(0.8)
        self.play(FadeIn(flash, scale=3.0), run_time=0.5){result_code}
        alive_wait(self, {max(duration - 7.0, 1.0):.1f}, particles=bg)'''

    def _choreo_bar_chart(self, clip, duration, images_dir):
        visuals = clip.get("visuals", {})
        cue_words = visuals.get("cue_words", [])
        params = {}
        for cue in cue_words:
            params.update(cue.get("params", {}))
        items = params.get("items", [])
        if isinstance(items, str): items = [items]
        bar_time = max(duration - 2.0, 1.0) / max(len(items), 1)
        code = "        # Bar chart\n"
        for i, item in enumerate(items):
            parts = item.split(":")
            label = parts[0] if len(parts) > 0 else f"Item {i}"
            value = parts[1] if len(parts) > 1 else "0"
            color = parts[2].upper() if len(parts) > 2 else "GLOW"
            y = 2.0 - i * 1.0
            bw = min(float(value) / 25000 * 8, 8.0) if value.replace(",","").isdigit() else 4.0
            code += f'''        bar_{i} = Rectangle(width={bw:.1f}, height=0.5, color={color}, fill_color={color}, fill_opacity=0.3, stroke_width=2)
        bar_{i}.move_to(LEFT * {(8-bw)/2:.1f} + UP * {y:.1f})
        bar_{i}_l = Text("{label}", font="Courier", color={color}, weight=BOLD).scale(0.3)
        bar_{i}_l.next_to(bar_{i}, LEFT, buff=0.3)
        bar_{i}_v = Text("{value}", font="Courier", color={color}).scale(0.35)
        bar_{i}_v.next_to(bar_{i}, RIGHT, buff=0.2)
        self.play(GrowFromEdge(bar_{i}, LEFT), FadeIn(bar_{i}_l), FadeIn(bar_{i}_v), run_time={bar_time:.1f})
'''
        code += f"        alive_wait(self, 1.0, particles=bg)"
        return code

    def _choreo_before_after(self, clip, duration, images_dir):
        visuals = clip.get("visuals", {})
        cue_words = visuals.get("cue_words", [])
        params = {}
        for cue in cue_words:
            params.update(cue.get("params", {}))
        label = params.get("label", "Metric")
        before = params.get("before", "0")
        after = params.get("after", "0")
        color = str(params.get("color", "gold")).upper()
        return f'''        # Before/After: {label}
        header = Text("{label}", font="Courier", color=TEXT_COL, weight=BOLD).scale(0.5)
        header.move_to(UP * 2.5)
        self.play(FadeIn(header), run_time=0.5)
        before_lbl = Text("BEFORE", font="Courier", color=TEXT_DIM).scale(0.35)
        before_lbl.move_to(LEFT * 3 + UP * 1.2)
        before_val = Text("{before}", font="Courier", color=TEXT_DIM, weight=BOLD).scale(0.8)
        before_val.move_to(LEFT * 3)
        self.play(FadeIn(before_lbl), FadeIn(before_val), run_time=1.0)
        alive_wait(self, {duration * 0.2:.1f}, particles=bg)
        arrow = Arrow(LEFT * 1, RIGHT * 1, color=GLOW, stroke_width=3)
        self.play(GrowArrow(arrow), run_time=0.8)
        after_lbl = Text("AFTER", font="Courier", color={color}).scale(0.35)
        after_lbl.move_to(RIGHT * 3 + UP * 1.2)
        after_val = Text("{after}", font="Courier", color={color}, weight=BOLD).scale(0.8)
        after_val.move_to(RIGHT * 3)
        self.play(FadeIn(after_lbl), FadeIn(after_val, scale=1.3), run_time=1.0)
        throb_title(self, after_val, cycles=1, scale_factor=1.05)
        alive_wait(self, {max(duration - 6.0, 1.0):.1f}, particles=bg)'''

    def _choreo_organism_reveal(self, clip, duration, images_dir):
        visuals = clip.get("visuals", {})
        cue_words = visuals.get("cue_words", [])
        word_times = clip.get("word_times", [])
        label_code_parts = []
        label_count = 0
        for cue in cue_words:
            event = cue.get("event", "")
            params = cue.get("params", {})
            idx = cue.get("at_index", 0)
            t = word_times[idx]["start"] if idx < len(word_times) else 0
            if event in ("show_name", "show_note", "show_structure"):
                text = params.get("name", params.get("note", params.get("structure", "")))
                color = {"show_name": palette["gold"], "show_note": palette["cyan"],
                         "show_structure": palette["purple"]}[event]
                i = label_count
                label_code_parts.append(f'''
        # Cue: {event} at {t:.2f}s
        current_time_{i} = self.renderer.time if hasattr(self.renderer, 'time') else 0
        wait_{i} = max(0, {t:.2f} - current_time_{i})
        if wait_{i} > 0:
            self.wait(wait_{i})
        lbl_{i} = Text("{text}", color="{color}", font_size=22)
        lbl_box_{i} = SurroundingRectangle(lbl_{i}, color="{color}",
                                            fill_color="{palette['bg']}", fill_opacity=0.85,
                                            buff=0.15, corner_radius=0.05)
        lbl_group_{i} = VGroup(lbl_box_{i}, lbl_{i})
        frame = self.layers.get('content', {{}}).get('asset_0', None)
        if frame:
            lbl_group_{i}.next_to(frame, RIGHT, buff=0.8).shift(DOWN * {i * 0.9 - 0.5})
            pointer_{i} = Line(
                frame.get_right() + RIGHT * 0.1,
                lbl_group_{i}.get_left() + LEFT * 0.1,
                color="{color}", stroke_width=1.5,
            )
            self.play(Create(pointer_{i}), FadeIn(lbl_group_{i}, shift=RIGHT * 0.2), run_time=0.8)
        else:
            lbl_group_{i}.move_to(RIGHT * 2 + DOWN * {i * 0.9 - 0.5})
            self.play(FadeIn(lbl_group_{i}, shift=RIGHT * 0.2), run_time=0.8)
        self.wait(0.3)''')
                label_count += 1
        labels_block = "\n".join(label_code_parts)
        hold = max(duration - 2.0 - label_count * 1.1, 0.5)
        return f'''        # Organism reveal with cue-synced labels
{labels_block}
        alive_wait(self, {hold:.1f}, particles=bg)'''

    def _choreo_data_text(self, clip, duration, images_dir):
        visuals = clip.get("visuals", {})
        cue_words = visuals.get("cue_words", [])
        word_times = clip.get("word_times", [])
        display_text = ""
        show_time = 0.2
        for cue in cue_words:
            if cue.get("event") == "show_text":
                display_text = cue.get("params", {}).get("text", "")
                idx = cue.get("at_index", 0)
                if idx < len(word_times):
                    show_time = word_times[idx].get("start", 0.2)
                break
        if not display_text:
            display_text = clip.get("text", "")
        display_text = display_text.replace('"', '\\"').replace("\n", " ")
        has_bullets = "\u00b7" in display_text or "\\n" in display_text
        if has_bullets:
            items = [s.strip() for s in display_text.replace("\\n", "\u00b7").split("\u00b7") if s.strip()]
            items_code = ""
            for i, item in enumerate(items):
                item_safe = item.replace('"', '\\"').replace("\n", " ")
                items_code += f'\n        item_{i} = Text("{item_safe}", color=TEXT_COL, font_size=48)\n        if item_{i}.width > 10:\n            item_{i}.scale(9.5 / item_{i}.width)\n        items.add(item_{i})'
            return f'''        # Data text (multi-line): show at {show_time:.2f}s
        if {show_time} > 0.05:
            self.wait({show_time})
        items = VGroup()
{items_code}
        items.arrange(DOWN, buff=0.5, aligned_edge=LEFT)
        items.move_to(ORIGIN)
        for i, item in enumerate(items):
            self.play(FadeIn(item, shift=RIGHT * 0.3), run_time=0.3)
            self.wait(0.15)
        alive_wait(self, max({duration} - {show_time} - len(items) * 0.45 - 1.0, 0.3), particles=bg)'''
        else:
            return f'''        # Data text: show at {show_time:.2f}s
        if {show_time} > 0.05:
            self.wait({show_time})
        txt = Text("{display_text}", color=TEXT_COL, font_size=64, weight=BOLD)
        if txt.width > 12:
            txt.scale(11.5 / txt.width)
        self.play(FadeIn(txt, shift=UP * 0.2), run_time=0.3)
        alive_wait(self, max({duration} - {show_time} - 1.0, 0.3), particles=bg)'''

    def _choreo_svg_reveal(self, clip, duration, images_dir):
        return f'''        # SVG reveal — content layer handles asset, choreo holds
        alive_wait(self, {max(duration - 2.0, 1.0):.1f}, particles=bg)'''

    def _choreo_ambient_field(self, clip, duration, images_dir):
        return f'''        # Ambient field — breathing pause
        line = Line(LEFT * 2, RIGHT * 2, color=GOLD, stroke_width=1, stroke_opacity=0.3)
        self.add(line)
        alive_wait(self, {duration:.1f}, particles=bg)'''

    def _choreo_title(self, clip, duration, images_dir):
        from docugen.tools.title import build_title_script
        import json as _json
        from pathlib import Path as _Path

        visuals = clip.get("visuals", {})
        cue_words = visuals.get("cue_words", [])
        params = {}
        for cue in cue_words:
            params.update(cue.get("params", {}))
        reveal_style = params.get("reveal_style", "particle")

        build_dir = _Path(images_dir).parent / "build"
        plan_path = build_dir / "plan.json"
        if plan_path.exists():
            plan = _json.loads(plan_path.read_text())
            meta = plan.get("meta", plan)
            title_text = meta.get("title", "Untitled")
            subtitle_text = meta.get("subtitle", "")
            plan_palette = meta.get("color_palette", {})
        else:
            title_text = "Untitled"
            subtitle_text = ""
            plan_palette = {}

        colors = {
            "bg": plan_palette.get("bg", palette["bg"]),
            "accent_gold": plan_palette.get("accent_gold", palette["gold"]),
            "accent_cyan": plan_palette.get("accent_cyan", palette["cyan"]),
            "glow": palette["glow"],
            "grid": palette["grid"],
            "text": plan_palette.get("text", palette["text"]),
        }

        font_dir = str(_Path(__file__).resolve().parent.parent.parent.parent / "assets" / "fonts")
        full_script = build_title_script(title_text, subtitle_text, reveal_style,
                                         duration, colors, font_dir)
        lines = full_script.split("\n")
        body_lines = []
        in_body = False
        # Skip theme setup lines — the fused renderer's theme layer handles these
        skip_patterns = ("hex_grid", "floating_particles", "imperial_border",
                         "make_hex_grid", "make_floating_bg", "grid =", "particles =",
                         "border =", "self.add(grid", "self.add(particles",
                         "self.add(border", "self.play(Create(border")
        for line in lines:
            if "def construct(self):" in line:
                in_body = True
                continue
            if in_body:
                stripped = line.strip()
                if any(p in stripped for p in skip_patterns):
                    continue
                body_lines.append(line)
        return "\n".join(body_lines) if body_lines else "        pass"

    def transition_sounds(self) -> dict[str, callable]:
        return {
            "imperial_chime": transition_imperial_chime,
            "dark_swell": transition_dark_swell,
            "crystal_ping": transition_crystal_ping,
            "heartbeat": transition_heartbeat,
            "bell": transition_bell,
            "sonar": transition_sonar,
            "resolve": transition_resolve,
            "tension": transition_tension,
        }

    def chapter_layers(self) -> dict[str, callable]:
        return {
            "intro": _layer_intro,
            "ch1_paper": _layer_ch1,
            "ch2_method": _layer_ch2,
            "ch3_scale": _layer_ch3,
            "ch4_anchor": _layer_ch4,
            "ch5_dark": _layer_ch5,
            "ch6_holdout": _layer_ch6,
            "ch7_synergy": _layer_ch7,
            "ch8_organisms": _layer_ch8,
            "ch9_future": _layer_ch9,
            "outro": _layer_outro,
        }


theme = BiopunkTheme()
