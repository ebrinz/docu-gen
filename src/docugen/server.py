"""Docugen MCP Server — documentary generation pipeline."""

from mcp.server.fastmcp import FastMCP

from docugen.tools.init_project import init_project
from docugen.tools.plan import extract_pdf_text, generate_plan
from docugen.split import split_plan
from docugen.align import align_plan
from docugen.tools.narrate import generate_narration
from docugen.tools.render import render_all
from docugen.tools.score import generate_score
from docugen.tools.stitch import stitch_all
from docugen.tools.title import generate_title
from docugen.spot import spot_project

mcp = FastMCP("docugen", instructions=(
    "Documentary generation pipeline. Use tools in order: "
    "init -> plan -> split -> narrate -> align -> direct_prepare -> direct_apply -> spot -> render -> score -> stitch. "
    "Use title to generate a standalone title card. "
    "Review and edit clips.json between steps to adjust "
    "emotion, pacing, visual direction, and cue words per clip."
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
    """Generate TTS narration audio for each clip, then re-align word timestamps.

    Reads build/clips.json, creates build/narration/{clip_id}.wav
    with per-clip emotion. Converts numbers to words and consolidates
    short clips before synthesis. Skips existing files.

    After narration, automatically runs Whisper alignment to update
    word_times in clips.json — this keeps visual cues synced to speech.

    Args:
        project_path: Path to project directory.
    """
    narr_result = generate_narration(project_path)
    align_result = align_plan(project_path)
    return narr_result + "\n\n" + align_result


@mcp.tool()
def align(project_path: str) -> str:
    """Align narration audio with text using Whisper word timestamps.

    Runs Whisper on each clip WAV, cross-correlates with ground-truth
    narration text, and saves word-level timestamps to clips.json.
    Choreography primitives use these to sync visuals with speech.

    Args:
        project_path: Path to project directory.
    """
    return align_plan(project_path)


@mcp.tool()
def direct_prepare(project_path: str) -> str:
    """Gather context for creative direction.

    Reads production plan visual descriptions, clips.json with word_times,
    and available assets. Returns a formatted summary for you (the MCP client)
    to reason about and generate creative direction JSON.

    Call direct_apply with the resulting JSON to validate and write it.

    Args:
        project_path: Path to project directory.
    """
    from docugen.direct import direct_prepare as _prepare
    return _prepare(project_path)


@mcp.tool()
def direct_apply(project_path: str, direction_json: str) -> str:
    """Apply creative direction JSON to clips.json.

    Validates slide types, assets, cue words, layouts, and transitions.
    Computes WAV-derived timing for all clips. Writes back to clips.json.

    Args:
        project_path: Path to project directory.
        direction_json: JSON string — clip_id keys, direction object values.
    """
    from docugen.direct import direct_apply as _apply
    return _apply(project_path, direction_json)


@mcp.tool()
def title(project_path: str, title_text: str = "",
          subtitle_text: str = "", reveal_style: str = "particle") -> str:
    """Generate a title card video clip.

    Uses Rajdhani font with configurable reveal animation.
    Styles: particle (default), glitch, trace, typewriter.

    Args:
        project_path: Path to project directory.
        title_text: Main title (defaults to production plan title).
        subtitle_text: Subtitle (defaults to production plan subtitle).
        reveal_style: Animation style.
    """
    return generate_title(project_path, title_text, subtitle_text, reveal_style)


@mcp.tool()
def spot(project_path: str) -> str:
    """Build audio cue sheet from visual direction + timing.

    Walks every clip's cue_words, computes global timestamps, maps events
    to audio spans (tension builds, hits, sweeps, ticks, etc.) using the
    slide registry's span patterns. Writes build/cue_sheet.json for the
    score tool to consume.

    Run after direct_apply, before render.

    Args:
        project_path: Path to project directory.
    """
    return spot_project(project_path)


@mcp.tool()
def render(project_path: str) -> str:
    """Render Manim video scenes for each clip.

    Reads build/clips.json and dispatches each clip to the appropriate
    slide type renderer. Uses cue_words from clips.json to sync visuals
    with narration. Creates build/clips/{clip_id}.mp4 using the project's theme.
    Skips existing files.

    Args:
        project_path: Path to project directory.
    """
    return render_all(project_path)


@mcp.tool()
def score(project_path: str) -> str:
    """Generate the drone score with chapter-specific layers.

    Reads build/clips.json and uses the timing model from WAV durations
    to place layers precisely. Creates build/score.wav with per-chapter
    drone layers and transition sounds from the project's theme.

    Args:
        project_path: Path to project directory.
    """
    return generate_score(project_path)


@mcp.tool()
def stitch(project_path: str) -> str:
    """Assemble clips, narration, and score into final video.

    Concatenates build/clips/*.mp4, mixes narration with score using the
    timing model for precise audio placement (voice-activated ducking),
    outputs build/final.mp4.

    Args:
        project_path: Path to project directory.
    """
    return stitch_all(project_path)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
