"""Init tool: create a new project directory with theme selection."""

from pathlib import Path
import yaml

from docugen.themes import list_themes


def init_project(project_name: str, theme: str = "biopunk") -> str:
    """Create a new project directory with starter files."""
    project_path = Path("projects") / project_name
    if project_path.exists():
        return f"Project already exists: {project_path}"

    project_path.mkdir(parents=True)
    (project_path / "images").mkdir()
    (project_path / "build").mkdir()

    available = list_themes()
    if theme not in available:
        theme = "biopunk"

    config = {
        "title": project_name.replace("-", " ").replace("_", " ").title(),
        "theme": theme,
        "voice": {"engine": "openai", "model": "tts-1-hd", "voice": "echo"},
        "video": {"resolution": "1080p", "fps": 60},
        "drone": {"cutoff_hz": 400, "duck_db": -18, "rt60": 1.5},
    }
    with open(project_path / "config.yaml", "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    (project_path / "prompt.txt").write_text(
        "Create a clear, engaging documentary that explains the key concepts.\n"
        "Use a calm, authoritative tone. Break into logical chapters.\n"
    )

    return (
        f"Project created: {project_path}\n"
        f"Theme: {theme}\n"
        f"Available themes: {', '.join(available)}\n\n"
        f"Next: add spec.pdf + images, then run plan_prepare -> plan_apply -> "
        f"split -> narrate -> viz_extract -> direct_prepare -> direct_apply -> "
        f"spot -> render -> score -> stitch"
    )
