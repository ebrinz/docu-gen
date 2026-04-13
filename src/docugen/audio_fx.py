"""Audio FX synthesis for cue sheet spans.

Each function takes (duration, sr) and returns a mono numpy array.
The spot tool maps event types to these via AUDIO_TREATMENTS.
"""

import numpy as np

SR = 44100


def _envelope(n: int, curve: str) -> np.ndarray:
    """Generate an intensity envelope for a span."""
    t = np.linspace(0, 1, n)
    if curve == "ramp_up":
        return t ** 1.5
    elif curve == "ramp_down":
        return (1 - t) ** 1.5
    elif curve == "spike":
        # Quick attack, medium decay
        attack = int(n * 0.1)
        env = np.zeros(n)
        env[:attack] = np.linspace(0, 1, attack)
        env[attack:] = np.exp(-3.0 * np.linspace(0, 1, n - attack))
        return env
    elif curve == "sustain":
        # Gentle fade in/out, sustain in middle
        fade = int(n * 0.1)
        env = np.ones(n)
        if fade > 0:
            env[:fade] = np.linspace(0, 1, fade)
            env[-fade:] = np.linspace(1, 0, fade)
        return env
    elif curve == "ease_in":
        return t ** 2.5
    elif curve == "linear":
        return np.ones(n)
    return np.ones(n)


def hit(duration: float, sr: int = SR, curve: str = "spike") -> np.ndarray:
    """Percussive impact — gold bell tone."""
    n = int(duration * sr)
    env = _envelope(n, curve)
    t = np.arange(n) / sr
    # Bell harmonics in D minor
    tone = (0.6 * np.sin(2 * np.pi * 293.66 * t) +    # D4
            0.3 * np.sin(2 * np.pi * 440.0 * t) +     # A4
            0.1 * np.sin(2 * np.pi * 587.33 * t))      # D5
    return tone * env * 0.4


def tension_build(duration: float, sr: int = SR, curve: str = "ramp_up") -> np.ndarray:
    """Filtered noise swell with rising cutoff."""
    n = int(duration * sr)
    env = _envelope(n, curve)
    rng = np.random.default_rng(42)
    noise = rng.standard_normal(n)
    # Rising lowpass via simple windowed average that shrinks
    from scipy.signal import butter, sosfilt
    out = np.zeros(n)
    chunk = max(n // 8, 1)
    for i in range(8):
        start = i * chunk
        end = min(start + chunk, n)
        cutoff = 200 + i * 400  # 200Hz → 3400Hz
        cutoff = min(cutoff, sr // 2 - 1)
        sos = butter(2, cutoff, btype="low", fs=sr, output="sos")
        out[start:end] = sosfilt(sos, noise[start:end])
    return out * env * 0.25


def sweep_tone(duration: float, sr: int = SR, curve: str = "linear") -> np.ndarray:
    """Gliding frequency sweep — scanline feel."""
    n = int(duration * sr)
    env = _envelope(n, curve)
    t = np.arange(n) / sr
    # Sweep from 800Hz to 2000Hz
    freq = 800 + (2000 - 800) * t / max(t[-1], 0.01)
    phase = 2 * np.pi * np.cumsum(freq) / sr
    return np.sin(phase) * env * 0.15


def tick_accelerate(duration: float, sr: int = SR, curve: str = "ramp_up") -> np.ndarray:
    """Clicks with decreasing interval — counter building."""
    n = int(duration * sr)
    env = _envelope(n, curve)
    out = np.zeros(n)
    # Ticks: start at 4/s, end at 20/s
    t = 0.0
    interval = 0.25  # start at 4/s
    click_len = int(0.005 * sr)
    click = np.sin(2 * np.pi * 1000 * np.arange(click_len) / sr)
    click *= np.exp(-10 * np.arange(click_len) / sr)
    while t < duration:
        idx = int(t * sr)
        end = min(idx + click_len, n)
        actual = end - idx
        if actual > 0:
            out[idx:end] += click[:actual]
        progress = t / max(duration, 0.01)
        interval = 0.25 * (1 - progress) + 0.05 * progress  # 4/s → 20/s
        t += interval
    return out * env * 0.3


def sting(duration: float, sr: int = SR, curve: str = "spike") -> np.ndarray:
    """Short harmonic burst — counter completion."""
    n = int(duration * sr)
    env = _envelope(n, curve)
    t = np.arange(n) / sr
    # D major chord burst
    tone = (0.5 * np.sin(2 * np.pi * 293.66 * t) +
            0.3 * np.sin(2 * np.pi * 369.99 * t) +
            0.2 * np.sin(2 * np.pi * 440.0 * t))
    return tone * env * 0.35


def swoosh(duration: float, sr: int = SR, curve: str = "ease_in") -> np.ndarray:
    """Soft reveal whoosh — noise burst with bandpass sweep."""
    n = int(duration * sr)
    env = _envelope(n, curve)
    rng = np.random.default_rng(7)
    noise = rng.standard_normal(n) * 0.3
    # Quick bandpass sweep
    from scipy.signal import butter, sosfilt
    cutoff = min(3000, sr // 2 - 1)
    sos = butter(2, [500, cutoff], btype="band", fs=sr, output="sos")
    filtered = sosfilt(sos, noise)
    return filtered * env * 0.2


def blip(duration: float, sr: int = SR, curve: str = "spike") -> np.ndarray:
    """Short data blip — single cycle ping."""
    n = int(duration * sr)
    env = _envelope(n, curve)
    t = np.arange(n) / sr
    return np.sin(2 * np.pi * 1200 * t) * env * 0.2


def swell_hit(duration: float, sr: int = SR, curve: str = "spike") -> np.ndarray:
    """Harmonic swell into impact — dot merge."""
    n = int(duration * sr)
    env = _envelope(n, curve)
    t = np.arange(n) / sr
    # Two tones converging
    f1 = 220 + 80 * t / max(t[-1], 0.01)
    f2 = 330 - 80 * t / max(t[-1], 0.01)
    phase1 = 2 * np.pi * np.cumsum(f1) / sr
    phase2 = 2 * np.pi * np.cumsum(f2) / sr
    return (np.sin(phase1) + np.sin(phase2)) * 0.5 * env * 0.3


def trace_hum(duration: float, sr: int = SR, curve: str = "sustain") -> np.ndarray:
    """Sustained sine at theme frequency — pointer drawing."""
    n = int(duration * sr)
    env = _envelope(n, curve)
    t = np.arange(n) / sr
    return np.sin(2 * np.pi * 220 * t) * env * 0.1


def tick(duration: float, sr: int = SR, curve: str = "ease_in") -> np.ndarray:
    """Single tick — bar chart bar appearing."""
    n = int(duration * sr)
    env = _envelope(n, curve)
    t = np.arange(n) / sr
    click = np.sin(2 * np.pi * 800 * t) * np.exp(-15 * t)
    return click * env * 0.25


def morph_tone(duration: float, sr: int = SR, curve: str = "linear") -> np.ndarray:
    """Gliding pitch shift — before/after morph."""
    n = int(duration * sr)
    env = _envelope(n, curve)
    t = np.arange(n) / sr
    freq = 220 + 220 * t / max(t[-1], 0.01)  # 220Hz → 440Hz
    phase = 2 * np.pi * np.cumsum(freq) / sr
    return np.sin(phase) * env * 0.15


def fade_down(duration: float, sr: int = SR, curve: str = "ramp_down") -> np.ndarray:
    """Descending tone — compound removal."""
    n = int(duration * sr)
    env = _envelope(n, curve)
    t = np.arange(n) / sr
    freq = 440 - 220 * t / max(t[-1], 0.01)
    phase = 2 * np.pi * np.cumsum(freq) / sr
    return np.sin(phase) * env * 0.15


def rise(duration: float, sr: int = SR, curve: str = "ramp_up") -> np.ndarray:
    """Ascending tone — compound reveal."""
    n = int(duration * sr)
    env = _envelope(n, curve)
    t = np.arange(n) / sr
    freq = 220 + 220 * t / max(t[-1], 0.01)
    phase = 2 * np.pi * np.cumsum(freq) / sr
    return np.sin(phase) * env * 0.15


# Dispatch table: audio treatment name -> synthesis function
SYNTH = {
    "hit": hit,
    "tension_build": tension_build,
    "sweep_tone": sweep_tone,
    "tick_accelerate": tick_accelerate,
    "sting": sting,
    "swoosh": swoosh,
    "blip": blip,
    "swell_hit": swell_hit,
    "trace_hum": trace_hum,
    "tick": tick,
    "morph_tone": morph_tone,
    "fade_down": fade_down,
    "rise": rise,
}


def render_cue_sheet(cue_sheet: list[dict], total_duration: float,
                     sr: int = SR) -> np.ndarray:
    """Render all cue sheet spans into a stereo audio track.

    Returns numpy array (n_samples, 2).
    """
    n = int(total_duration * sr)
    track = np.zeros((n, 2))

    for span in cue_sheet:
        audio_name = span.get("audio", "")
        synth_fn = SYNTH.get(audio_name)
        if not synth_fn:
            continue

        duration = span.get("duration", 0.3)
        curve = span.get("curve", "spike")
        start_sec = span.get("start", 0)

        # Synthesize
        mono = synth_fn(duration, sr, curve)

        # Place in stereo track
        start_sample = int(start_sec * sr)
        end_sample = min(start_sample + len(mono), n)
        actual = end_sample - start_sample
        if actual > 0:
            track[start_sample:end_sample, 0] += mono[:actual]
            track[start_sample:end_sample, 1] += mono[:actual]

    return track
