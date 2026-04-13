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

    def idle_scene(self, duration: float) -> str:
        return self.manim_header() + f'''

class Scene_idle(Scene):
    def construct(self):
        grid = make_hex_grid(rows=10, cols=16, radius=0.35)
        self.add(grid)
        bg = make_floating_bg()
        self.add(bg)
        border = imperial_border()
        self.play(Create(border), run_time=2.0)
        alive_wait(self, {max(duration - 2.0, 0.5):.1f}, particles=bg)
'''

    def chapter_card(self, num: str, title: str, duration: float) -> str:
        hold = max(duration - 4.0, 1.0)
        return self.manim_header() + f'''

class Scene_chapter_card(Scene):
    def construct(self):
        grid = make_hex_grid(rows=8, cols=14, radius=0.3, opacity=0.08)
        self.add(grid)
        border = imperial_border()
        self.add(border)
        bg = make_floating_bg()
        self.add(bg)

        ch_num = Text("{num}", font="Courier", color=SITH_RED, weight=BOLD).scale(1.5)
        ch_title = Text("{title}", font="Courier", color=GLOW, weight=BOLD).scale(0.9)
        ch_title.next_to(ch_num, RIGHT, buff=0.4)
        card = VGroup(ch_num, ch_title).move_to(ORIGIN)
        self.play(FadeIn(card, shift=RIGHT * 0.3), run_time=1.0)
        throb_title(self, ch_title, cycles=2, scale_factor=1.03, cycle_time=1.0)
        alive_wait(self, {hold:.1f}, particles=bg)
        self.play(*[FadeOut(m) for m in self.mobjects], run_time=1.0)
'''

    def image_reveal(self, assets: list[str], direction: str,
                     duration: float, images_dir: str) -> str:
        n = max(len(assets), 1)
        per_asset = duration / n
        asset_blocks = ""
        for asset in assets:
            # Use os.path.join at Manim runtime to handle paths robustly
            asset_path = asset.replace("\\", "/")
            asset_blocks += f'''
        # Asset: {asset_path}
        try:
            if "{asset_path}".lower().endswith(".svg"):
                img = SVGMobject("{asset_path}").scale(2.5)
            else:
                img = ImageMobject("{asset_path}").scale_to_fit_width(10)
            img.set_opacity(0)
            self.add(img)
            self.play(img.animate.set_opacity(1.0).scale(1.04),
                      run_time=min(2.0, {per_asset:.1f} * 0.4), rate_func=smooth)
            alive_wait(self, {max(per_asset - 3.0, 0.5):.1f}, particles=bg)
            self.play(FadeOut(img), run_time=min(1.0, {per_asset:.1f} * 0.2))
        except Exception:
            alive_wait(self, {per_asset:.1f}, particles=bg)
'''
        return self.manim_header() + f'''

class Scene_image_reveal(Scene):
    def construct(self):
        grid = make_hex_grid(rows=8, cols=14, radius=0.3, opacity=0.08)
        self.add(grid)
        border = imperial_border()
        self.add(border)
        bg = make_floating_bg()
        self.add(bg)
        # Direction: {direction}
{asset_blocks}
        self.play(*[FadeOut(m) for m in self.mobjects], run_time=1.0)
'''

    def data_reveal(self, direction: str, duration: float) -> str:
        hold = max(duration - 4.0, 1.0)
        # Escape any braces in the direction string so they don't confuse Manim
        safe_direction = direction.replace('"', '\\"')
        return self.manim_header() + f'''

class Scene_data_reveal(Scene):
    def construct(self):
        grid = make_hex_grid(rows=8, cols=14, radius=0.3, opacity=0.08)
        self.add(grid)
        border = imperial_border()
        self.add(border)
        bg = make_floating_bg()
        self.add(bg)

        label = Text("{safe_direction}", font="Courier", color=GLOW, weight=BOLD)
        label.scale(0.55).move_to(ORIGIN)
        label.set_opacity(0)
        self.play(label.animate.set_opacity(1.0), run_time=1.5, rate_func=smooth)
        throb_title(self, label, cycles=2, scale_factor=1.03, cycle_time=1.0)
        alive_wait(self, {hold:.1f}, particles=bg)
        self.play(*[FadeOut(m) for m in self.mobjects], run_time=1.0)
'''

    def custom_animation(self, direction: str, duration: float,
                         assets: list[str], images_dir: str) -> str:
        hold = max(duration - 4.0, 1.0)
        safe_direction = direction.replace('"', '\\"')
        return self.manim_header() + f'''

class Scene_custom_animation(Scene):
    def construct(self):
        grid = make_hex_grid(rows=8, cols=14, radius=0.3, opacity=0.08)
        self.add(grid)
        border = imperial_border()
        self.add(border)
        bg = make_floating_bg()
        self.add(bg)

        # Choreography: {safe_direction}
        label = Text("{safe_direction[:60]}...", font="Courier", color=TEXT_COL)
        label.scale(0.4).to_edge(DOWN, buff=0.5)
        self.play(FadeIn(label), run_time=0.5)
        scanline(self, duration=2.0, color=PURPLE)
        alive_wait(self, {hold:.1f}, particles=bg)
        self.play(*[FadeOut(m) for m in self.mobjects], run_time=1.0)
'''

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
