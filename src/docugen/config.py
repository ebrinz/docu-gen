"""Load and validate project config.yaml with defaults."""

from pathlib import Path
import yaml

DEFAULTS = {
    "voice": {
        "model": "tts-1-hd",
        "voice": "echo",
    },
    "video": {
        "resolution": "1080p",
        "fps": 60,
    },
    "drone": {
        "cutoff_hz": 400,
        "duck_db": -18,
        "rt60": 1.5,
        "cue_freq": 220,
    },
}


def _deep_merge(defaults: dict, overrides: dict) -> dict:
    """Merge overrides into defaults, recursing into nested dicts."""
    result = dict(defaults)
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(project_path: str | Path) -> dict:
    """Load config.yaml from a project directory, applying defaults."""
    project_path = Path(project_path)
    config_file = project_path / "config.yaml"
    if not config_file.exists():
        raise FileNotFoundError(f"No config.yaml in {project_path}")

    with open(config_file) as f:
        raw = yaml.safe_load(f) or {}

    return _deep_merge(DEFAULTS, raw)
