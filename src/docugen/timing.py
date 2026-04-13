"""Timing model: compute per-clip duration and chapter offsets from WAV + word_times.

All timing derives from actual audio data. No hardcoded buffers.
"""

from pathlib import Path
from scipy.io import wavfile

PACING_TARGETS = {"tight": 0.5, "normal": 1.5, "breathe": 3.0}
FIXED_CARD_DURATION = 3.0


def get_wav_duration(wav_path: str | Path) -> float:
    """Measure WAV file duration in seconds."""
    sr, data = wavfile.read(str(wav_path))
    if data.ndim > 1:
        data = data[:, 0]
    return len(data) / sr


def compute_clip_timing(clip: dict, wav_duration: float,
                        chapter_offset: float) -> dict:
    """Compute timing fields for a single clip.

    Args:
        clip: Clip dict with word_times and pacing fields.
        wav_duration: Measured WAV duration (0.0 if no narration).
        chapter_offset: Cumulative time from chapter start.

    Returns:
        Timing dict with wav_duration, speech_start, speech_end,
        trailing_silence, pacing_pad, clip_duration, chapter_offset.
    """
    word_times = clip.get("word_times", [])
    pacing = clip.get("pacing", "normal")

    # No narration — fixed duration chapter card
    if not word_times or wav_duration <= 0:
        return {
            "wav_duration": 0.0,
            "speech_start": 0.0,
            "speech_end": 0.0,
            "trailing_silence": 0.0,
            "pacing_pad": 0.0,
            "clip_duration": FIXED_CARD_DURATION,
            "chapter_offset": chapter_offset,
        }

    speech_start = word_times[0].get("start", 0.0)
    speech_end = word_times[-1].get("end", wav_duration)
    trailing_silence = max(0.0, wav_duration - speech_end)

    target_pad = PACING_TARGETS.get(pacing, 1.5)
    pacing_pad = max(0.0, target_pad - trailing_silence)

    clip_duration = wav_duration + pacing_pad

    return {
        "wav_duration": wav_duration,
        "speech_start": speech_start,
        "speech_end": speech_end,
        "trailing_silence": round(trailing_silence, 3),
        "pacing_pad": round(pacing_pad, 3),
        "clip_duration": round(clip_duration, 3),
        "chapter_offset": round(chapter_offset, 3),
    }


def compute_chapter_timeline(clips: list[dict]) -> list[float]:
    """Compute chapter_offset for each clip from its timing.clip_duration.

    Args:
        clips: List of clip dicts, each with timing.clip_duration set.

    Returns:
        List of chapter_offset floats, one per clip.
    """
    offsets = []
    offset = 0.0
    for clip in clips:
        offsets.append(round(offset, 3))
        offset += clip.get("timing", {}).get("clip_duration", 3.0)
    return offsets
