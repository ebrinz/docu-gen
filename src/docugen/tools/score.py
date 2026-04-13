"""Score tool: generate drone score with theme-driven chapter layers."""

import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from docugen.config import load_config
from docugen.drone import generate_drone_track, SR


def _get_wav_duration(path: Path) -> float:
    sr, data = wavfile.read(str(path))
    if data.ndim > 1:
        data = data[:, 0]
    return len(data) / sr


def _build_timeline(project_path: Path, clips_data: dict) -> list[dict]:
    """Build chapter-level timeline from clip timing model.

    Falls back to WAV measurement if timing model not yet computed.
    """
    narr_dir = project_path / "build" / "narration"
    timeline = []
    global_offset = 0.0

    for chapter in clips_data["chapters"]:
        ch_start = global_offset
        ch_dur = 0.0
        for clip in chapter["clips"]:
            timing = clip.get("timing", {})
            clip_dur = timing.get("clip_duration", 0)

            # Fallback: measure WAV if timing not yet computed
            if clip_dur <= 0:
                clip_id = clip["clip_id"]
                wav_path = narr_dir / f"{clip_id}.wav"
                if wav_path.exists():
                    clip_dur = _get_wav_duration(wav_path)
                else:
                    clip_dur = 3.0
                pacing = clip.get("pacing", "normal")
                clip_dur += {"tight": 0.5, "normal": 1.5, "breathe": 3.5}.get(pacing, 1.5)

            ch_dur += clip_dur

        timeline.append({
            "id": chapter["id"],
            "start": ch_start,
            "dur": ch_dur,
        })
        global_offset += ch_dur

    return timeline


def generate_score(project_path: str | Path) -> str:
    """Generate the drone score from clips.json + theme layers.

    Reads build/clips.json for timeline, uses theme for chapter-specific
    drone layers and transition sounds. Falls back to plan.json for legacy.

    Returns summary string.
    """
    project_path = Path(project_path)
    config = load_config(project_path)
    drone_config = config["drone"]
    build_dir = project_path / "build"

    # Determine timeline source
    clips_path = build_dir / "clips.json"
    plan_path = build_dir / "plan.json"

    if clips_path.exists():
        clips_data = json.loads(clips_path.read_text())
        timeline = _build_timeline(project_path, clips_data)
        theme_name = clips_data.get("theme", config.get("theme", "biopunk"))
    elif plan_path.exists():
        plan = json.loads(plan_path.read_text())
        narr_dir = build_dir / "narration"
        timeline = []
        offset = 0.0
        for ch in plan["chapters"]:
            wav_path = narr_dir / f"{ch['id']}.wav"
            dur = _get_wav_duration(wav_path) if wav_path.exists() else ch.get("duration_s", 30)
            timeline.append({"id": ch["id"], "start": offset, "dur": dur})
            offset += dur
        theme_name = config.get("theme", "biopunk")
    else:
        raise FileNotFoundError("No clips.json or plan.json found.")

    total_dur = timeline[-1]["start"] + timeline[-1]["dur"] + 5.0
    chapter_start_times = [t["start"] for t in timeline]

    # Generate base drone
    drone = generate_drone_track(
        total_duration=total_dur,
        chapter_start_times=chapter_start_times,
        cutoff_hz=drone_config["cutoff_hz"],
        cue_freq=drone_config.get("cue_freq", 220),
        rt60=drone_config["rt60"],
        sr=SR,
    )

    # Overlay theme-specific layers if theme available
    try:
        from docugen.themes import load_theme
        theme = load_theme(theme_name)

        # Chapter layers
        layers = theme.chapter_layers()
        for ch_info in timeline:
            cid = ch_info["id"]
            if cid in layers:
                start_sample = int(ch_info["start"] * SR)
                dur_samples = int(ch_info["dur"] * SR)
                rng = np.random.default_rng(hash(cid) & 0xFFFFFFFF)
                layer = layers[cid](dur_samples, SR, rng)
                # Crossfade
                xfade = min(int(1.0 * SR), dur_samples // 4)
                if xfade > 0:
                    layer[:xfade] *= np.linspace(0, 1, xfade)
                    layer[-xfade:] *= np.linspace(1, 0, xfade)
                end = min(start_sample + len(layer), drone.shape[0])
                actual = end - start_sample
                if actual > 0 and drone.ndim == 2:
                    drone[start_sample:end, 0] += layer[:actual]
                    drone[start_sample:end, 1] += layer[:actual]
                elif actual > 0:
                    drone[start_sample:end] += layer[:actual]

        # Transition sounds
        sounds = theme.transition_sounds()
        for ch_info in timeline:
            cid = ch_info["id"]
            if cid in sounds:
                trans = sounds[cid]()
                start = max(0, int(ch_info["start"] * SR) - int(0.5 * SR))
                end = min(start + len(trans), drone.shape[0])
                actual = end - start
                if actual > 0 and drone.ndim == 2:
                    drone[start:end, 0] += trans[:actual] * 0.4
                    drone[start:end, 1] += trans[:actual] * 0.4
                elif actual > 0:
                    drone[start:end] += trans[:actual] * 0.4
    except (ValueError, ImportError):
        pass  # No theme layers available, use base drone only

    # Overlay cue sheet audio FX if available
    cue_sheet_path = build_dir / "cue_sheet.json"
    if cue_sheet_path.exists():
        try:
            from docugen.audio_fx import render_cue_sheet
            cue_sheet = json.loads(cue_sheet_path.read_text())
            if cue_sheet:
                fx_track = render_cue_sheet(cue_sheet, total_dur, SR)
                # Trim/pad to match drone length
                if fx_track.shape[0] > drone.shape[0]:
                    fx_track = fx_track[:drone.shape[0]]
                elif fx_track.shape[0] < drone.shape[0]:
                    pad = np.zeros((drone.shape[0] - fx_track.shape[0], 2))
                    fx_track = np.vstack([fx_track, pad])
                drone += fx_track
        except Exception:
            pass  # FX are optional — don't break the score if synthesis fails

    # Normalize
    peak = np.max(np.abs(drone)) + 1e-10
    drone = drone / peak * 0.9

    # Write
    score_path = build_dir / "score.wav"
    output = np.clip(drone * 32767, -32768, 32767).astype(np.int16)
    wavfile.write(str(score_path), SR, output)

    return f"Score generated: {score_path} ({total_dur:.1f}s)"
