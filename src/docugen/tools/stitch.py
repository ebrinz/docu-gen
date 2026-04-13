"""Stitch tool: combine clips + narration + drone into final video."""

import json
import subprocess
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter

from docugen.config import load_config
# drone import removed — score tool handles generation now

SR = 44100


def db_to_amp(db: float) -> float:
    return 10.0 ** (db / 20.0)


def _resample(data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Resample audio data from orig_sr to target_sr using linear interpolation."""
    if orig_sr == target_sr:
        return data
    ratio = target_sr / orig_sr
    new_len = int(len(data) * ratio)
    indices = np.arange(new_len) / ratio
    if data.ndim == 1:
        return np.interp(indices, np.arange(len(data)), data)
    return np.column_stack([
        np.interp(indices, np.arange(len(data)), data[:, ch])
        for ch in range(data.shape[1])
    ])


def _read_wav_float(path: Path) -> tuple[int, np.ndarray]:
    sr, data = wavfile.read(str(path))
    if data.dtype == np.int16:
        data = data.astype(np.float64) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float64) / 2147483648.0
    elif data.dtype == np.float32:
        data = data.astype(np.float64)
    # Resample to target SR if needed
    if sr != SR:
        data = _resample(data, sr, SR)
        sr = SR
    return sr, data


def _mono_to_stereo(data: np.ndarray) -> np.ndarray:
    if data.ndim == 1:
        return np.column_stack([data, data])
    return data


def _pad_or_trim(data: np.ndarray, target: int) -> np.ndarray:
    if data.shape[0] >= target:
        return data[:target]
    if data.ndim == 1:
        return np.pad(data, (0, target - data.shape[0]))
    padding = np.zeros((target - data.shape[0], data.shape[1]))
    return np.vstack([data, padding])


def load_narration_tracks(project_path: Path) -> dict:
    """Load narration WAV files and return metadata dict."""
    project_path = Path(project_path)
    narration_dir = project_path / "build" / "narration"
    plan = json.loads((project_path / "build" / "plan.json").read_text())

    tracks = {}
    for chapter in plan["chapters"]:
        cid = chapter["id"]
        wav_path = narration_dir / f"{cid}.wav"
        if wav_path.exists():
            sr, data = _read_wav_float(wav_path)
            data = _mono_to_stereo(data)
            tracks[cid] = {
                "path": wav_path,
                "duration": data.shape[0] / sr,
                "data": data,
                "sr": sr,
            }
    return tracks


def mix_audio(voice: np.ndarray, drone: np.ndarray, duck_db: float = -18,
              sr: int = SR) -> np.ndarray:
    """Mix voice and drone with voice-activated ducking."""
    mono_voice = voice.mean(axis=1) if voice.ndim > 1 else voice
    window_samples = int(0.1 * sr)
    squared = mono_voice ** 2
    window = np.ones(window_samples) / window_samples
    rms = np.sqrt(np.convolve(squared, window, mode="same"))

    threshold = db_to_amp(-40)
    duck_amount = db_to_amp(duck_db)
    active = (rms > threshold).astype(np.float64)

    coeff = 1.0 / max(int(0.2 * sr), 1)
    b = [coeff]
    a = [1.0, -(1.0 - coeff)]
    smoothed = lfilter(b, a, active)
    smoothed = np.clip(smoothed, 0.0, 1.0)

    gain = 1.0 - smoothed * (1.0 - duck_amount)
    drone[:, 0] *= gain
    drone[:, 1] *= gain

    drone_level = db_to_amp(-18)
    mixed = voice + drone * drone_level

    peak = np.max(np.abs(mixed)) + 1e-10
    target_peak = db_to_amp(-1)
    mixed = mixed * (target_peak / peak)

    return mixed


def _concatenate_clips(project_path: Path, plan: dict) -> Path:
    """Concatenate chapter clips in order using FFmpeg."""
    clips_dir = project_path / "build" / "clips"
    build_dir = project_path / "build"

    concat_file = build_dir / "concat.txt"
    lines = []
    for chapter in plan["chapters"]:
        clip = clips_dir / f"{chapter['id']}.mp4"
        if clip.exists():
            lines.append(f"file '{clip}'")
    concat_file.write_text("\n".join(lines))

    concat_video = build_dir / "concat.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(concat_video),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg concat failed:\n{result.stderr}")
    return concat_video


def _get_video_duration(video_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def _build_concat_file(project_path: Path, clips_data: dict) -> Path:
    """Generate ffmpeg concat file from clips.json clip IDs."""
    clips_dir = project_path / "build" / "clips"
    build_dir = project_path / "build"
    concat_file = build_dir / "concat.txt"

    lines = []
    for chapter in clips_data["chapters"]:
        for clip in chapter["clips"]:
            clip_path = clips_dir / f"{clip['clip_id']}.mp4"
            if clip_path.exists():
                lines.append(f"file '{clip_path.resolve()}'")
    concat_file.write_text("\n".join(lines))
    return concat_file


def _stitch_from_clips(project_path: Path) -> str:
    """Stitch from clips.json — assembly only."""
    config = load_config(project_path)
    build_dir = project_path / "build"
    clips_data = json.loads((build_dir / "clips.json").read_text())

    # Concat video clips
    concat_file = _build_concat_file(project_path, clips_data)
    concat_video = build_dir / "concat.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", str(concat_file), "-c", "copy", str(concat_video)],
        capture_output=True, text=True, check=True,
    )
    video_duration = _get_video_duration(concat_video)
    total_samples = int(video_duration * SR)

    # Build voice track from per-clip WAVs
    voice = np.zeros((total_samples, 2))
    narr_dir = build_dir / "narration"
    global_offset = 0.0
    for chapter in clips_data["chapters"]:
        for clip in chapter["clips"]:
            clip_id = clip["clip_id"]
            timing = clip.get("timing", {})
            clip_duration = timing.get("clip_duration", 0)

            wav_path = narr_dir / f"{clip_id}.wav"
            if wav_path.exists():
                _, data = _read_wav_float(wav_path)
                data = _mono_to_stereo(data)
                start = int(global_offset * SR)
                end = min(start + data.shape[0], total_samples)
                actual = end - start
                if actual > 0:
                    voice[start:end] = data[:actual]

            # Advance by timing model duration (includes pacing pad)
            if clip_duration > 0:
                global_offset += clip_duration
            else:
                # Fallback: WAV duration + pacing buffer
                if wav_path.exists():
                    global_offset += data.shape[0] / SR
                else:
                    global_offset += 3.0
                pacing = clip.get("pacing", "normal")
                global_offset += {"tight": 0.5, "normal": 1.5, "breathe": 3.5}.get(pacing, 1.5)

    # Load pre-generated score
    score_path = build_dir / "score.wav"
    if score_path.exists():
        _, score = _read_wav_float(score_path)
        score = _mono_to_stereo(score)
        score = _pad_or_trim(score, total_samples)
    else:
        score = np.zeros((total_samples, 2))

    # Mix
    duck_db = config["drone"]["duck_db"]
    mixed = mix_audio(voice, score, duck_db=duck_db, sr=SR)

    # Write and mux
    mixed_wav = build_dir / "mixed_audio.wav"
    wavfile.write(str(mixed_wav), SR,
                  np.clip(mixed * 32767, -32768, 32767).astype(np.int16))

    final_path = build_dir / "final.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(concat_video), "-i", str(mixed_wav),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
         str(final_path)],
        capture_output=True, text=True, check=True,
    )

    concat_file.unlink(missing_ok=True)
    concat_video.unlink(missing_ok=True)

    return f"Final video: {final_path} ({video_duration:.1f}s)"


def _stitch_from_plan(project_path: Path) -> str:
    """Legacy stitch from plan.json — generates drone inline."""
    from docugen.drone import generate_drone_track

    config = load_config(project_path)
    drone_config = config["drone"]
    build_dir = project_path / "build"

    plan = json.loads((build_dir / "plan.json").read_text())
    concat_video = _concatenate_clips(project_path, plan)
    video_duration = _get_video_duration(concat_video)

    tracks = load_narration_tracks(project_path)
    total_samples = int(video_duration * SR)
    voice_full = np.zeros((total_samples, 2))

    offset = 0.0
    chapter_start_times = []
    for chapter in plan["chapters"]:
        cid = chapter["id"]
        chapter_start_times.append(offset)
        if cid in tracks:
            track_data = tracks[cid]["data"]
            start_sample = int(offset * SR)
            end_sample = min(start_sample + track_data.shape[0], total_samples)
            voice_full[start_sample:end_sample] = track_data[:end_sample - start_sample]
            offset += tracks[cid]["duration"]
        else:
            offset += chapter.get("duration_estimate", 10.0)

    drone = generate_drone_track(
        total_duration=video_duration,
        chapter_start_times=chapter_start_times,
        cutoff_hz=drone_config["cutoff_hz"],
        cue_freq=drone_config["cue_freq"],
        rt60=drone_config["rt60"],
        sr=SR,
    )
    drone = _pad_or_trim(drone, total_samples)
    mixed = mix_audio(voice_full, drone, duck_db=drone_config["duck_db"], sr=SR)

    mixed_wav = build_dir / "mixed_audio.wav"
    wavfile.write(str(mixed_wav), SR,
                  np.clip(mixed * 32767, -32768, 32767).astype(np.int16))

    final_path = build_dir / "final.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(concat_video), "-i", str(mixed_wav),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
         str(final_path)],
        capture_output=True, text=True, check=True,
    )

    (build_dir / "concat.txt").unlink(missing_ok=True)
    concat_video.unlink(missing_ok=True)

    return f"Final video: {final_path} ({video_duration:.1f}s)"


def stitch_all(project_path: str | Path) -> str:
    """Assemble clips, narration, and score into final video.

    Uses clips.json if available (per-clip assembly with pre-generated score).
    Falls back to plan.json (legacy, generates drone inline).
    """
    project_path = Path(project_path)
    build_dir = project_path / "build"

    if (build_dir / "clips.json").exists():
        return _stitch_from_clips(project_path)
    if (build_dir / "plan.json").exists():
        return _stitch_from_plan(project_path)
    raise FileNotFoundError("No clips.json or plan.json found.")
