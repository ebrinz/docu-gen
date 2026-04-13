"""Narrate tool: generate TTS audio per clip or per chapter."""

import json
import time
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from openai import OpenAI

from docugen.config import load_config
from docugen.numberwords import numbers_to_words

TARGET_SR = 44100


def _read_wav_duration(path: Path) -> float:
    """Get duration of a WAV file in seconds."""
    sr, data = wavfile.read(str(path))
    if data.ndim > 1:
        data = data[:, 0]
    return len(data) / sr


# ---------------------------------------------------------------------------
# OpenAI TTS
# ---------------------------------------------------------------------------

def _generate_openai(client, clip_id: str, text: str, model: str,
                     voice: str, output_path: Path, speed: float = 1.0) -> Path:
    """Call OpenAI TTS. Retries with exponential backoff."""
    if output_path.exists():
        return output_path

    for attempt in range(3):
        try:
            response = client.audio.speech.create(
                model=model, voice=voice, input=text,
                response_format="wav", speed=speed,
            )
            response.write_to_file(str(output_path))
            return output_path
        except Exception:
            if attempt < 2:
                time.sleep(2 ** (attempt + 1))
            else:
                raise


# ---------------------------------------------------------------------------
# Chatterbox MLX TTS
# ---------------------------------------------------------------------------

_chatterbox_model = None


def _get_chatterbox_model():
    """Lazy-load the Chatterbox MLX model (heavy; load once per session)."""
    global _chatterbox_model
    if _chatterbox_model is None:
        from chatterbox.tts_mlx import ChatterboxTTSMLX
        _chatterbox_model = ChatterboxTTSMLX.from_pretrained(device="mps")
    return _chatterbox_model


def _apply_post_fx(wav_np: np.ndarray, sr: int, post_fx: dict) -> np.ndarray:
    """Apply robotic post-processing FX to a waveform."""
    import scipy.signal as sig

    ring_freq = post_fx.get("ring_freq", 0)
    formant_shift = post_fx.get("formant_shift", 1.0)
    dry_wet = post_fx.get("dry_wet", 0.0)

    if dry_wet <= 0:
        return wav_np

    t = np.arange(len(wav_np)) / sr
    ring_mod = wav_np * np.sin(2 * np.pi * ring_freq * t) if ring_freq > 0 else np.zeros_like(wav_np)

    if formant_shift != 1.0:
        n_orig = len(wav_np)
        n_shift = int(n_orig / formant_shift)
        shifted = sig.resample(wav_np, n_shift)
        shifted = sig.resample(shifted, n_orig)
    else:
        shifted = np.zeros_like(wav_np)

    robotic = (1.0 - dry_wet) * wav_np + (dry_wet * 0.5) * ring_mod + (dry_wet * 0.5) * shifted
    peak = np.abs(robotic).max()
    if peak > 0:
        robotic = robotic / peak * 0.95
    return robotic.astype(np.float32)


def _generate_chatterbox(voice_config: dict, text: str,
                         output_path: Path,
                         exaggeration: float | None = None) -> Path:
    """Generate a single WAV using Chatterbox MLX with voice cloning."""
    import torchaudio as ta

    if output_path.exists():
        return output_path

    model = _get_chatterbox_model()

    ref_audio = voice_config.get("ref_audio")
    if ref_audio is None:
        raise ValueError("voice.ref_audio is required when engine is 'chatterbox'")

    exagg = exaggeration if exaggeration is not None else voice_config.get("exaggeration", 0.5)

    wav = model.generate(
        text,
        audio_prompt_path=ref_audio,
        exaggeration=exagg,
        cfg_weight=voice_config.get("cfg_weight", 0.5),
    )

    wav_np = wav.squeeze().numpy()

    post_fx = voice_config.get("post_fx")
    if post_fx:
        wav_np = _apply_post_fx(wav_np, model.sr, post_fx)

    ta.save(str(output_path),
            __import__("torch").from_numpy(wav_np).unsqueeze(0),
            model.sr)
    return output_path


# ---------------------------------------------------------------------------
# Short clip consolidation (Chatterbox)
# ---------------------------------------------------------------------------

SHORT_WORD_LIMIT = 6
HIGH_EXAGGERATION = 0.3


def _detect_short_hot_clips(clips: list[dict]) -> list[int]:
    """Find clips that are short + high exaggeration (Chatterbox failure mode).

    Returns list of indices into the clips list.
    """
    indices = []
    for i, clip in enumerate(clips):
        word_count = len(clip.get("word_times", []))
        if word_count == 0:
            word_count = len(clip.get("text", "").split())
        exagg = clip.get("exaggeration", 0.0)
        if word_count <= SHORT_WORD_LIMIT and exagg >= HIGH_EXAGGERATION:
            indices.append(i)
    return indices


def _plan_consolidation(clips: list[dict],
                        short_indices: list[int]) -> list[dict]:
    """Plan which short clips merge into which neighbors.

    Prefers merging into the preceding clip (setup to punchline).
    Returns list of {"merge_into": int, "short_index": int}.
    """
    plan = []
    for idx in short_indices:
        if idx > 0:
            plan.append({"merge_into": idx - 1, "short_index": idx})
        elif idx < len(clips) - 1:
            plan.append({"merge_into": idx + 1, "short_index": idx})
    return plan


# ---------------------------------------------------------------------------
# Clip-based generation (new pipeline)
# ---------------------------------------------------------------------------

def _generate_from_clips(project_path: Path, config: dict) -> str:
    """Generate one WAV per clip from clips.json."""
    voice_config = config["voice"]
    engine = voice_config.get("engine", "openai")

    clips_data = json.loads((project_path / "build" / "clips.json").read_text())
    narration_dir = project_path / "build" / "narration"
    narration_dir.mkdir(parents=True, exist_ok=True)

    client = OpenAI() if engine == "openai" else None
    results = []

    for chapter in clips_data["chapters"]:
        for clip in chapter["clips"]:
            clip_id = clip["clip_id"]
            text = clip.get("text", "")
            if not text.strip():
                continue  # skip empty clips (chapter cards with no narration)

            # Convert numeric symbols to natural English for cleaner TTS
            text = numbers_to_words(text)

            out_path = narration_dir / f"{clip_id}.wav"

            if engine == "chatterbox":
                _generate_chatterbox(voice_config, text, out_path,
                                     exaggeration=clip.get("exaggeration"))
            else:
                _generate_openai(
                    client, clip_id, text,
                    model=voice_config["model"],
                    voice=voice_config["voice"],
                    output_path=out_path,
                )

            if out_path.exists():
                duration = _read_wav_duration(out_path)
                results.append(f"{clip_id}.wav ({duration:.1f}s)")

    return "Generated narration:\n" + "\n".join(results)


# ---------------------------------------------------------------------------
# Legacy chapter-based generation
# ---------------------------------------------------------------------------

def _generate_from_plan(project_path: Path, config: dict) -> str:
    """Generate one WAV per chapter from plan.json (backwards compat)."""
    voice_config = config["voice"]
    engine = voice_config.get("engine", "openai")

    plan = json.loads((project_path / "build" / "plan.json").read_text())
    narration_dir = project_path / "build" / "narration"
    narration_dir.mkdir(parents=True, exist_ok=True)

    client = OpenAI() if engine == "openai" else None
    results = []

    for chapter in plan["chapters"]:
        cid = chapter["id"]
        text = numbers_to_words(chapter["narration"])
        out_path = narration_dir / f"{cid}.wav"

        if engine == "chatterbox":
            _generate_chatterbox(voice_config, text, out_path,
                                 exaggeration=chapter.get("exaggeration"))
        else:
            _generate_openai(
                client, cid, text,
                model=voice_config["model"],
                voice=voice_config["voice"],
                output_path=out_path,
            )

            duration = _read_wav_duration(out_path)
            estimate = chapter.get("duration_estimate", 999)

            if duration > estimate:
                for speed in [1.1, 1.15, 1.2, 1.25]:
                    out_path.unlink(missing_ok=True)
                    _generate_openai(
                        client, cid, text,
                        model=voice_config["model"],
                        voice=voice_config["voice"],
                        output_path=out_path,
                        speed=speed,
                    )
                    duration = _read_wav_duration(out_path)
                    if duration <= estimate:
                        break

        duration = _read_wav_duration(out_path)
        results.append(f"{cid}.wav ({duration:.1f}s)")

    return "Generated narration:\n" + "\n".join(results)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_narration(project_path: str | Path) -> str:
    """Generate TTS narration WAVs.

    Uses clips.json if available (per-clip generation with per-clip emotion).
    Falls back to plan.json (per-chapter generation) for legacy projects.
    """
    project_path = Path(project_path)
    config = load_config(project_path)

    clips_path = project_path / "build" / "clips.json"
    if clips_path.exists():
        return _generate_from_clips(project_path, config)

    plan_path = project_path / "build" / "plan.json"
    if plan_path.exists():
        return _generate_from_plan(project_path, config)

    raise FileNotFoundError("No clips.json or plan.json found. Run 'split' or 'plan' first.")
