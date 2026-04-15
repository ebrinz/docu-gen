"""Audio synth renderer — generates per-clip cue sounds using numpy synthesis."""
from __future__ import annotations
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from docugen.renderers import register_renderer

_SR = 44100

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

    # Placeholder — future renderers (audio_clap, audio_gen) will generate actual cue sounds
    wavfile.write(str(out_path), _SR, audio)
    return out_path

register_renderer("audio_synth", render_node)
