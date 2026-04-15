"""Audio synth renderer — generates per-clip cue sounds using numpy synthesis."""
from __future__ import annotations
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

from docugen.renderers import register_renderer

_SR = 44100


# ── Synthesis primitives ──────────────────────────────────────────────


def _sine(freq, dur):
    t = np.arange(int(dur * _SR)) / _SR
    return np.sin(2 * np.pi * freq * t)


def _envelope(sig, attack=0.01, decay=0.05):
    n = len(sig)
    env = np.ones(n)
    a = min(int(attack * _SR), n)
    d = min(int(decay * _SR), n)
    if a > 0:
        env[:a] = np.linspace(0, 1, a)
    if d > 0:
        env[-d:] = np.linspace(1, 0, d)
    return sig * env


def _lowpass(sig, cutoff):
    sos = butter(4, cutoff, btype="low", fs=_SR, output="sos")
    return sosfilt(sos, sig)


def _noise(n_samples):
    return np.random.default_rng(42).standard_normal(n_samples).astype(np.float32)


# ── Cue sound generators ─────────────────────────────────────────────
# Each returns a numpy array at _SR sample rate, mono, normalized to [-1, 1]


def _gen_blip(duration, curve):
    """Short sine ping — data point appearing."""
    dur = min(duration, 0.15)
    sig = _sine(880, dur) * 0.6 + _sine(1320, dur) * 0.3
    sig = _envelope(sig, attack=0.005, decay=0.08)
    return sig * 0.7


def _gen_tick(duration, curve):
    """Single click."""
    dur = min(duration, 0.05)
    sig = _sine(2000, dur)
    sig = _envelope(sig, attack=0.002, decay=0.03)
    return sig * 0.5


def _gen_tick_accelerate(duration, curve):
    """Series of clicks with decreasing interval."""
    n_ticks = 12
    total = int(duration * _SR)
    out = np.zeros(total, dtype=np.float32)
    tick = _gen_tick(0.03, "spike")
    tick_len = len(tick)
    for i in range(n_ticks):
        # Exponential acceleration: ticks get closer together
        t = (1 - (1 - i / n_ticks) ** 2) * duration
        idx = int(t * _SR)
        end = min(idx + tick_len, total)
        seg = end - idx
        if seg > 0:
            out[idx:end] += tick[:seg] * (0.3 + 0.7 * i / n_ticks)
    return out * 0.7


def _gen_sting(duration, curve):
    """Short harmonic burst — counter completion, emphasis."""
    dur = min(duration, 0.4)
    sig = _sine(440, dur) * 0.5 + _sine(660, dur) * 0.3 + _sine(880, dur) * 0.2
    sig = _envelope(sig, attack=0.005, decay=0.25)
    return sig * 0.7


def _gen_swoosh(duration, curve):
    """Filtered noise sweep — reveal, transition."""
    dur = min(duration, 1.0)
    n = int(dur * _SR)
    noise = _noise(n)
    # Sweep cutoff from high to low
    out = np.zeros(n, dtype=np.float32)
    chunk = max(n // 20, 1)
    for i in range(0, n, chunk):
        end = min(i + chunk, n)
        progress = i / n
        cutoff = 8000 * (1 - progress) + 200 * progress
        seg = noise[i:end]
        out[i:end] = _lowpass(np.pad(seg, (100, 100)), cutoff)[100:100 + end - i]
    out = _envelope(out, attack=0.02, decay=0.15)
    return out * 0.5


def _gen_fade_down(duration, curve):
    """Descending sine glide."""
    dur = min(duration, 1.0)
    t = np.arange(int(dur * _SR)) / _SR
    freq = 440 * np.exp(-2 * t / dur)
    sig = np.sin(2 * np.pi * np.cumsum(freq) / _SR)
    sig = _envelope(sig, attack=0.01, decay=0.2)
    return sig.astype(np.float32) * 0.5


def _gen_rise(duration, curve):
    """Ascending sine glide."""
    dur = min(duration, 0.8)
    t = np.arange(int(dur * _SR)) / _SR
    freq = 220 * np.exp(2 * t / dur)
    sig = np.sin(2 * np.pi * np.cumsum(freq) / _SR)
    sig = _envelope(sig, attack=0.02, decay=0.1)
    return sig.astype(np.float32) * 0.5


def _gen_trace_hum(duration, curve):
    """Sustained sine at theme frequency."""
    sig = _sine(220, duration) * 0.3 + _sine(330, duration) * 0.15
    sig = _envelope(sig, attack=0.1, decay=0.3)
    return sig.astype(np.float32) * 0.4


def _gen_tension_build(duration, curve):
    """Filtered noise swell with rising cutoff."""
    n = int(duration * _SR)
    noise = _noise(n)
    t = np.arange(n) / _SR
    # Rising cutoff envelope
    cutoff = 200 + 3000 * (t / duration) ** 2
    out = np.zeros(n, dtype=np.float32)
    chunk = max(n // 30, 1)
    for i in range(0, n, chunk):
        end = min(i + chunk, n)
        mid = (i + end) // 2
        c = float(cutoff[min(mid, n - 1)])
        seg = noise[i:end]
        out[i:end] = _lowpass(np.pad(seg, (100, 100)), min(c, _SR * 0.45))[100:100 + end - i]
    # Ramp volume up
    out *= np.linspace(0, 1, n) ** 1.5
    out = _envelope(out, attack=0.05, decay=0.1)
    return out * 0.6


def _gen_swell_hit(duration, curve):
    """Harmonic swell into impact — merge, climax."""
    n = int(duration * _SR)
    # Swell phase (80% of duration)
    swell_n = int(n * 0.8)
    swell = _sine(220, swell_n / _SR) * np.linspace(0, 0.6, swell_n)
    swell += _sine(330, swell_n / _SR) * np.linspace(0, 0.3, swell_n)
    # Hit phase (20%)
    hit_n = n - swell_n
    hit = _sine(440, hit_n / _SR) * 0.8 + _sine(660, hit_n / _SR) * 0.4
    hit = _envelope(hit, attack=0.003, decay=0.15)
    out = np.concatenate([swell, hit])
    return out.astype(np.float32) * 0.7


# ── Generator dispatch ────────────────────────────────────────────────

_GENERATORS = {
    "blip": _gen_blip,
    "tick": _gen_tick,
    "tick_accelerate": _gen_tick_accelerate,
    "sting": _gen_sting,
    "swoosh": _gen_swoosh,
    "fade_down": _gen_fade_down,
    "rise": _gen_rise,
    "trace_hum": _gen_trace_hum,
    "tension_build": _gen_tension_build,
    "swell_hit": _gen_swell_hit,
}


# ── Renderer entry point ─────────────────────────────────────────────


def render_node(node, inputs, clip, project_path):
    """Generate audio cue sounds for a clip based on cue_words."""
    project_path = Path(project_path)
    clip_id = clip["clip_id"]
    clip_dir = project_path / "build" / "clips" / clip_id
    clip_dir.mkdir(parents=True, exist_ok=True)
    out_path = clip_dir / f"_node_{node['name']}.wav"

    timing = clip.get("timing", {})
    total_duration = timing.get("clip_duration", 5.0)
    n_samples = int(total_duration * _SR)
    audio = np.zeros(n_samples, dtype=np.float32)

    # Read cue_words and word_times to place sounds
    visuals = clip.get("visuals", {})
    cue_words = visuals.get("cue_words", [])
    word_times = clip.get("word_times", [])

    # Load the cue sheet spans for this clip (if available)
    cue_sheet_path = project_path / "build" / "cue_sheet.json"
    clip_spans = []
    if cue_sheet_path.exists():
        import json
        all_spans = json.loads(cue_sheet_path.read_text())
        # Get the clip's start offset from timing
        clip_start = timing.get("clip_start", 0)
        for span in all_spans:
            if span.get("clip_id") == clip_id:
                # Convert global time to clip-local time
                local_start = span["start"] - clip_start
                clip_spans.append({
                    "start": max(local_start, 0),
                    "duration": span["duration"],
                    "audio": span["audio"],
                    "curve": span["curve"],
                })

    # Title slide special treatment — tension build + chime hit
    slide_type = visuals.get("slide_type", "")
    if slide_type == "title" and not clip_spans:
        # Tension build for 70% of duration, then sting hit
        reveal_time = total_duration * 0.7
        clip_spans = [
            {"start": 0.0, "duration": reveal_time, "audio": "tension_build", "curve": "ramp_up"},
            {"start": reveal_time, "duration": 0.4, "audio": "sting", "curve": "spike"},
            {"start": reveal_time + 0.1, "duration": 1.5, "audio": "trace_hum", "curve": "sustain"},
        ]

    # If no cue sheet spans, derive from cue_words directly
    if not clip_spans:
        from docugen.themes.slides import SLIDE_REGISTRY
        registry_entry = SLIDE_REGISTRY.get(slide_type, {})
        span_templates = registry_entry.get("spans", [])

        for cue in cue_words:
            event = cue.get("event", "")
            idx = cue.get("at_index", 0)
            if idx < len(word_times):
                cue_time = word_times[idx].get("start", 0)
            else:
                cue_time = 0

            for tmpl in span_templates:
                if tmpl["trigger"] == event:
                    clip_spans.append({
                        "start": max(cue_time + tmpl.get("offset", 0), 0),
                        "duration": tmpl["duration"],
                        "audio": tmpl["audio"],
                        "curve": tmpl.get("curve", "spike"),
                    })

    # Generate and place each sound
    for span in clip_spans:
        audio_type = span["audio"]
        gen = _GENERATORS.get(audio_type)
        if not gen:
            continue

        sound = gen(span["duration"], span["curve"])
        start_sample = int(span["start"] * _SR)
        end_sample = min(start_sample + len(sound), n_samples)
        seg_len = end_sample - start_sample
        if seg_len > 0:
            audio[start_sample:end_sample] += sound[:seg_len]

    # Normalize — boost cue sounds to sit clearly in the mix
    peak = np.max(np.abs(audio))
    if peak > 0.01:
        audio = audio / peak * 0.95

    wavfile.write(str(out_path), _SR, audio)
    return out_path


register_renderer("audio_synth", render_node)
