"""Docugen MCP Server — documentary generation pipeline."""

from mcp.server.fastmcp import FastMCP

from docugen.tools.plan import extract_pdf_text, generate_plan
from docugen.tools.narrate import generate_narration
from docugen.tools.render import render_all
from docugen.tools.stitch import stitch_all

mcp = FastMCP("docugen", instructions=(
    "Documentary generation pipeline. Use tools in order: "
    "plan → narrate → render → stitch. "
    "Review artifacts between stages."
))


@mcp.tool()
def plan(project_path: str) -> str:
    """Extract text from spec.pdf and generate a chapter plan via AI.

    Creates build/plan.json with chapter structure, narration scripts,
    and image assignments. Review and edit plan.json before proceeding.

    Args:
        project_path: Path to project directory containing config.yaml,
                      spec.pdf, prompt.txt, and images/
    """
    pdf_text = extract_pdf_text(f"{project_path}/spec.pdf")
    return generate_plan(project_path, pdf_text=pdf_text)


@mcp.tool()
def narrate(project_path: str) -> str:
    """Generate TTS narration audio for each chapter in plan.json.

    Requires: build/plan.json (run 'plan' first).
    Creates: build/narration/*.wav (one per chapter).

    Uses OpenAI tts-1-hd with echo voice. Automatically adjusts
    speed if narration exceeds chapter duration estimate.

    Args:
        project_path: Path to project directory.
    """
    return generate_narration(project_path)


@mcp.tool()
def render(project_path: str) -> str:
    """Render Manim video scenes for each chapter.

    Requires: build/plan.json and build/narration/*.wav.
    Creates: build/clips/*.mp4 (one per chapter).

    Intro/outro get animated title cards. Mixed chapters get
    chapter cards + images with Ken Burns motion.

    Args:
        project_path: Path to project directory.
    """
    return render_all(project_path)


@mcp.tool()
def stitch(project_path: str) -> str:
    """Combine all clips, narration, and drone audio into final video.

    Requires: build/clips/*.mp4 and build/narration/*.wav.
    Creates: build/final.mp4.

    Synthesizes ambient drone with chapter transition cues,
    applies voice-activated ducking, and merges everything.

    Args:
        project_path: Path to project directory.
    """
    return stitch_all(project_path)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
