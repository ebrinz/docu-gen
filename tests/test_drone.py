import numpy as np
import pytest
from docugen.drone import (
    pink_noise, sine_wave, apply_envelope, synthetic_reverb_ir,
    generate_drone_track,
)


def test_pink_noise_shape():
    rng = np.random.default_rng(42)
    noise = pink_noise(44100, rng)
    assert noise.shape == (44100,)
    assert np.max(np.abs(noise)) <= 1.0 + 1e-6


def test_sine_wave_frequency():
    sr = 44100
    signal = sine_wave(440.0, 1.0, sr=sr)
    assert len(signal) == sr
    crossings = np.where(np.diff(np.sign(signal)))[0]
    assert 850 < len(crossings) < 910


def test_apply_envelope_shape():
    signal = np.ones(44100)
    enveloped = apply_envelope(signal, attack_s=0.1, decay_s=0.5)
    assert enveloped.shape == signal.shape
    assert enveloped[0] == pytest.approx(0.0, abs=0.01)


def test_synthetic_reverb_ir_decays():
    ir = synthetic_reverb_ir(rt60=1.0)
    quarter = len(ir) // 4
    first_energy = np.mean(ir[:quarter] ** 2)
    last_energy = np.mean(ir[-quarter:] ** 2)
    assert first_energy > last_energy * 10


def test_generate_drone_track_output():
    chapter_times = [0.0, 5.0, 10.0]
    total_duration = 15.0
    track = generate_drone_track(
        total_duration=total_duration,
        chapter_start_times=chapter_times,
        cutoff_hz=400,
        cue_freq=220,
        rt60=1.5,
        sr=44100,
    )
    expected_samples = int(total_duration * 44100)
    assert track.ndim == 2
    assert track.shape[1] == 2
    assert abs(track.shape[0] - expected_samples) < 44100
