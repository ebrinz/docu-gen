"""Drone audio synthesis — adapted from heiroglyphy/docs/audio/generate_drone.py.

Generates a stereo ambient drone with reactive cues at chapter transitions.
"""

import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve

SR = 44100


def db_to_amp(db: float) -> float:
    return 10.0 ** (db / 20.0)


def pink_noise(n_samples: int, rng: np.random.Generator) -> np.ndarray:
    """Generate pink noise using vectorized Voss-McCartney algorithm."""
    n_rows = 16
    array = rng.standard_normal((n_rows, n_samples))
    for i in range(1, n_rows):
        step = 2 ** i
        n_unique = (n_samples + step - 1) // step
        values = rng.standard_normal(n_unique)
        array[i, :] = np.repeat(values, step)[:n_samples]
    result = array.sum(axis=0)
    result /= np.max(np.abs(result)) + 1e-10
    return result


def sine_wave(freq: float, duration: float, sr: int = SR, phase: float = 0.0) -> np.ndarray:
    t = np.arange(int(duration * sr)) / sr
    return np.sin(2 * np.pi * freq * t + phase)


def apply_envelope(signal: np.ndarray, attack_s: float, decay_s: float,
                   sustain_s: float = 0.0, sr: int = SR) -> np.ndarray:
    n = len(signal)
    envelope = np.ones(n)
    attack_n = int(attack_s * sr)
    decay_n = int(decay_s * sr)
    sustain_n = int(sustain_s * sr)

    if attack_n > 0:
        envelope[:attack_n] = np.linspace(0, 1, attack_n) ** 2
    decay_start = attack_n + sustain_n
    if decay_start < n and decay_n > 0:
        decay_end = min(decay_start + decay_n, n)
        actual_decay = decay_end - decay_start
        envelope[decay_start:decay_end] = np.linspace(1, 0, actual_decay) ** 2
        envelope[decay_end:] = 0.0

    return signal * envelope


def synthetic_reverb_ir(rt60: float = 1.5, sr: int = SR,
                        rng: np.random.Generator | None = None) -> np.ndarray:
    if rng is None:
        rng = np.random.default_rng(0)
    n_samples = int(rt60 * 2 * sr)
    noise = rng.standard_normal(n_samples)
    decay = np.exp(-3.0 * np.arange(n_samples) / (rt60 * sr))
    return noise * decay


def _bandpass(signal: np.ndarray, low: float, high: float,
              sr: int = SR, order: int = 4) -> np.ndarray:
    sos = butter(order, [low, high], btype="band", fs=sr, output="sos")
    return sosfilt(sos, signal)


def _lowpass(signal: np.ndarray, cutoff: float,
             sr: int = SR, order: int = 4) -> np.ndarray:
    sos = butter(order, cutoff, btype="low", fs=sr, output="sos")
    return sosfilt(sos, signal)


def _generate_base(total_samples: int, rng: np.random.Generator,
                   sr: int = SR) -> np.ndarray:
    """Base drone: fundamental + harmonics + pink noise. Returns stereo (N, 2)."""
    fundamental = 65.0
    duration = total_samples / sr

    drone = np.tanh(1.5 * sine_wave(fundamental, duration, sr))
    drone += db_to_amp(-6) * sine_wave(fundamental * 2, duration, sr)
    drone += db_to_amp(-12) * sine_wave(fundamental * 3, duration, sr)
    drone += db_to_amp(-18) * sine_wave(fundamental * 5, duration, sr)

    lfo = 1.0 + 0.15 * sine_wave(0.08, duration, sr)
    drone *= lfo

    noise = pink_noise(total_samples, rng)
    noise = _bandpass(noise, 100, 800, sr)
    noise *= db_to_amp(-24)
    drone += noise
    drone /= np.max(np.abs(drone)) + 1e-10

    left = drone
    right = np.tanh(1.5 * sine_wave(fundamental + 0.5, duration, sr))
    right += db_to_amp(-6) * sine_wave(fundamental * 2 + 0.5, duration, sr)
    right += db_to_amp(-12) * sine_wave(fundamental * 3 + 0.5, duration, sr)
    right += db_to_amp(-18) * sine_wave(fundamental * 5 + 0.5, duration, sr)
    right *= lfo
    right += noise
    right /= np.max(np.abs(right)) + 1e-10

    return np.column_stack([left, right])


def _generate_cue(freq: float, duration: float, attack: float,
                  decay: float, sr: int = SR) -> np.ndarray:
    """Generate a reactive sine cue. Returns stereo (N, 2)."""
    signal = sine_wave(freq, duration, sr)
    signal = apply_envelope(signal, attack_s=attack, decay_s=decay)
    signal *= db_to_amp(-12)
    return np.column_stack([signal, signal])


def _overlay(base: np.ndarray, layer: np.ndarray, start_sample: int) -> np.ndarray:
    """Overlay a stereo layer onto base at a given sample position."""
    if layer.ndim == 1:
        layer = np.column_stack([layer, layer])
    end = start_sample + layer.shape[0]
    if end > base.shape[0]:
        layer = layer[:base.shape[0] - start_sample]
        end = base.shape[0]
    if start_sample < base.shape[0]:
        base[start_sample:end] += layer
    return base


def generate_drone_track(
    total_duration: float,
    chapter_start_times: list[float],
    cutoff_hz: float = 400,
    cue_freq: float = 220,
    rt60: float = 1.5,
    sr: int = SR,
) -> np.ndarray:
    """Generate a complete drone track with chapter transition cues.

    Args:
        total_duration: Total duration in seconds.
        chapter_start_times: List of chapter start times for reactive cues.
        cutoff_hz: Low-pass filter cutoff.
        cue_freq: Frequency of transition cues.
        rt60: Reverb decay time.
        sr: Sample rate.

    Returns:
        Stereo numpy array (N, 2) of float64 samples, normalized.
    """
    total_samples = int(total_duration * sr)
    rng = np.random.default_rng(42)

    drone = _generate_base(total_samples, rng, sr)

    for t in chapter_start_times:
        cue = _generate_cue(cue_freq, 4.0, attack=0.1, decay=2.0, sr=sr)
        start_sample = int(t * sr)
        drone = _overlay(drone, cue, start_sample)

    drone[:, 0] = _lowpass(drone[:, 0], cutoff_hz, sr)
    drone[:, 1] = _lowpass(drone[:, 1], cutoff_hz, sr)

    ir = synthetic_reverb_ir(rt60=rt60, sr=sr, rng=rng)
    for ch in range(2):
        wet = fftconvolve(drone[:, ch], ir, mode="full")[:total_samples]
        drone[:, ch] = 0.7 * drone[:, ch] + 0.3 * wet

    fade_in = int(3.0 * sr)
    fade_out = int(5.0 * sr)
    drone[:fade_in, 0] *= np.linspace(0, 1, fade_in)
    drone[:fade_in, 1] *= np.linspace(0, 1, fade_in)
    drone[-fade_out:, 0] *= np.linspace(1, 0, fade_out)
    drone[-fade_out:, 1] *= np.linspace(1, 0, fade_out)

    peak = np.max(np.abs(drone)) + 1e-10
    drone = drone / peak * 0.9

    return drone
