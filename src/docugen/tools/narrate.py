"""Narrate tool: generate TTS audio for each chapter via OpenAI."""

import json
import time
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly
from math import gcd
from openai import OpenAI

from docugen.config import load_config

TARGET_SR = 44100


def _read_wav_duration(path: Path) -> float:
    """Get duration of a WAV file in seconds."""
    sr, data = wavfile.read(str(path))
    if data.ndim > 1:
        data = data[:, 0]
    return len(data) / sr


def _generate_single(client, chapter_id: str, text: str, model: str,
                     voice: str, output_path: Path, speed: float = 1.0) -> Path:
    """Call OpenAI TTS for a single chapter. Retries with exponential backoff."""
    if output_path.exists():
        return output_path

    for attempt in range(3):
        try:
            response = client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                response_format="wav",
                speed=speed,
            )
            response.write_to_file(str(output_path))
            return output_path
        except Exception as e:
            if attempt < 2:
                wait = 2 ** (attempt + 1)
                time.sleep(wait)
            else:
                raise


def generate_narration(project_path: str | Path) -> str:
    """Generate TTS narration WAVs for each chapter in plan.json.

    Returns a summary string listing generated files and durations.
    """
    project_path = Path(project_path)
    config = load_config(project_path)
    voice_config = config["voice"]

    plan_path = project_path / "build" / "plan.json"
    if not plan_path.exists():
        raise FileNotFoundError(f"No plan.json found. Run 'plan' first.")

    plan = json.loads(plan_path.read_text())
    narration_dir = project_path / "build" / "narration"
    narration_dir.mkdir(parents=True, exist_ok=True)

    client = OpenAI()
    results = []

    for chapter in plan["chapters"]:
        cid = chapter["id"]
        text = chapter["narration"]
        out_path = narration_dir / f"{cid}.wav"

        _generate_single(
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
                _generate_single(
                    client, cid, text,
                    model=voice_config["model"],
                    voice=voice_config["voice"],
                    output_path=out_path,
                    speed=speed,
                )
                duration = _read_wav_duration(out_path)
                if duration <= estimate:
                    break

        results.append(f"{cid}.wav ({duration:.1f}s)")

    return "Generated narration:\n" + "\n".join(results)
