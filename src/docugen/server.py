"""Docugen MCP Server — documentary generation pipeline."""

from mcp.server.fastmcp import FastMCP

from docugen.tools.init_project import init_project
from docugen.tools.plan import extract_pdf_text, generate_plan
from docugen.split import split_plan
from docugen.tools.narrate import generate_narration
from docugen.tools.render import render_all
from docugen.tools.score import generate_score
from docugen.tools.stitch import stitch_all

mcp = FastMCP("docugen", instructions=(
    "Documentary generation pipeline. Use tools in order: "
    "init -> plan -> split -> narrate -> render -> score -> stitch. "
    "Review and edit clips.json between split and narrate to adjust "
    "emotion, pacing, and visual direction per clip."
))


@mcp.tool()
def init(project_name: str, theme: str = "biopunk") -> str:
    """Create a new project directory with theme selection.

    Sets up project structure with config.yaml, images/, and prompt.txt.

    Args:
        project_name: Name for the project directory.
        theme: Visual theme module name (default: biopunk).
    """
    return init_project(project_name, theme)


@mcp.tool()
def plan(project_path: str) -> str:
    """Extract text from spec.pdf and generate a chapter plan via AI.

    Creates build/plan.json with chapter structure, narration scripts,
    and image assignments.

    Args:
        project_path: Path to project directory.
    """
    pdf_text = extract_pdf_text(f"{project_path}/spec.pdf")
    return generate_plan(project_path, pdf_text=pdf_text)


@mcp.tool()
def split(project_path: str) -> str:
    """Split chapters into clips with emotion tagging and pacing.

    Reads build/plan.json, produces build/clips.json. Each clip gets
    narration text, emotion exaggeration, pacing, and visual assignment.
    Edit clips.json to adjust before running narrate.

    Args:
        project_path: Path to project directory.
    """
    return split_plan(project_path)


@mcp.tool()
def narrate(project_path: str) -> str:
    """Generate TTS narration audio for each clip.

    Reads build/clips.json, creates build/narration/{clip_id}.wav
    with per-clip emotion. Skips existing files.

    Args:
        project_path: Path to project directory.
    """
    return generate_narration(project_path)


@mcp.tool()
def render(project_path: str) -> str:
    """Render Manim video scenes for each clip.

    Reads build/clips.json and narration WAV durations.
    Creates build/clips/{clip_id}.mp4 using the project's theme.
    Skips existing files.

    Args:
        project_path: Path to project directory.
    """
    return render_all(project_path)


@mcp.tool()
def score(project_path: str) -> str:
    """Generate the drone score with chapter-specific layers.

    Reads build/clips.json and narration WAV durations.
    Creates build/score.wav with per-chapter drone layers
    and transition sounds from the project's theme.

    Args:
        project_path: Path to project directory.
    """
    return generate_score(project_path)


@mcp.tool()
def stitch(project_path: str) -> str:
    """Assemble clips, narration, and score into final video.

    Concatenates build/clips/*.mp4, mixes narration with score
    (voice-activated ducking), outputs build/final.mp4.

    Args:
        project_path: Path to project directory.
    """
    return stitch_all(project_path)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
