"""Plan tool: host-driven chapter planning.

Split into two phases (same pattern as direct_prepare / direct_apply):

- plan_prepare: reads spec.pdf + prompt.txt + images/, returns a formatted
  context blob for the MCP host (Claude) to reason about and produce plan JSON.
- plan_apply: validates host-authored JSON and writes build/plan.json.

The old single-shot plan() is retained as an OpenAI fallback for environments
without an MCP host capable of planning (generate_plan_via_openai).
"""

import json
from pathlib import Path

import fitz  # PyMuPDF

from docugen.config import load_config


PLAN_SCHEMA_PROMPT = """\
Return a JSON object matching this schema:

{
  "title": "Documentary Title",
  "chapters": [
    {
      "id": "intro" | "ch1" | "ch2" | ... | "outro",
      "title": "Chapter Title",
      "narration": "Full narration script for voiceover.",
      "scene_type": "manim" | "mixed",
      "images": ["filename.png"],
      "duration_estimate": 30.0
    }
  ]
}

Rules:
- Always start with an "intro" chapter (scene_type: "manim", no images).
- Always end with an "outro" chapter (scene_type: "manim", no images).
- Content chapters use scene_type "mixed" and reference available images.
- Narration should be conversational, ~130 words per minute pace.
- duration_estimate in seconds, based on narration length.
- Assign images to the chapters where they are most relevant.
"""


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract all text from a PDF file using PyMuPDF."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    doc = fitz.open(str(pdf_path))
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


def list_images(project_path: Path) -> list[str]:
    """List image filenames in the project's images/ directory."""
    project_path = Path(project_path)
    images_dir = project_path / "images"
    if not images_dir.exists():
        return []
    extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    return sorted(
        f.name for f in images_dir.iterdir()
        if f.suffix.lower() in extensions
    )


def plan_prepare(project_path: str | Path) -> str:
    """Gather planning context. No API calls — host reasons on the return value."""
    project_path = Path(project_path)

    pdf_path = project_path / "spec.pdf"
    if not pdf_path.exists():
        slide_deck = project_path / "slide_deck.pdf"
        if slide_deck.exists():
            pdf_path = slide_deck
        else:
            raise FileNotFoundError(
                f"No spec.pdf or slide_deck.pdf at {project_path}"
            )

    pdf_text = extract_pdf_text(pdf_path)
    prompt_file = project_path / "prompt.txt"
    creative_prompt = prompt_file.read_text() if prompt_file.exists() else ""
    images = list_images(project_path)
    config = load_config(project_path)
    project_title = config.get("title", project_path.name)

    return (
        f"# Documentary Plan Context\n\n"
        f"## Project\n{project_title}\n\n"
        f"## Creative Direction\n{creative_prompt}\n\n"
        f"## Available Images\n{json.dumps(images, indent=2)}\n\n"
        f"## Source PDF Text\n{pdf_text}\n\n"
        f"## Output Format\n{PLAN_SCHEMA_PROMPT}\n\n"
        f"Call plan_apply(project_path, plan_json) with your JSON response."
    )


def _validate_plan(plan: dict) -> list[str]:
    """Return a list of validation errors; empty list = valid."""
    errors = []
    if not isinstance(plan, dict):
        return ["plan root must be an object"]
    if not plan.get("title"):
        errors.append("missing 'title'")
    chapters = plan.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        errors.append("'chapters' must be a non-empty list")
        return errors

    required = {"id", "title", "narration", "scene_type", "images", "duration_estimate"}
    for i, ch in enumerate(chapters):
        if not isinstance(ch, dict):
            errors.append(f"chapter[{i}] must be an object")
            continue
        missing = required - ch.keys()
        if missing:
            errors.append(f"chapter[{i}] ({ch.get('id','?')}) missing: {sorted(missing)}")
        if ch.get("scene_type") not in ("manim", "mixed"):
            errors.append(f"chapter[{i}] scene_type must be 'manim' or 'mixed'")
        if not isinstance(ch.get("images", []), list):
            errors.append(f"chapter[{i}] images must be a list")

    if chapters[0].get("id") != "intro":
        errors.append("first chapter id must be 'intro'")
    if chapters[-1].get("id") != "outro":
        errors.append("last chapter id must be 'outro'")
    return errors


def plan_apply(project_path: str | Path, plan_json: str) -> str:
    """Validate host-authored plan JSON and write build/plan.json."""
    project_path = Path(project_path)
    config = load_config(project_path)

    plan = json.loads(plan_json)
    if "title" not in plan or not plan["title"]:
        plan["title"] = config.get("title", "Untitled Documentary")

    errors = _validate_plan(plan)
    if errors:
        error_list = "\n".join(f"  - {e}" for e in errors)
        return f"plan_apply: validation failed:\n{error_list}"

    build_dir = project_path / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    plan_path = build_dir / "plan.json"
    plan_path.write_text(json.dumps(plan, indent=2) + "\n")

    n_chapters = len(plan["chapters"])
    return f"plan_apply: wrote {n_chapters} chapters to {plan_path}"


def generate_plan_via_openai(
    project_path: str | Path, pdf_text: str | None = None
) -> str:
    """OpenAI fallback for environments without an MCP host.

    Prefer plan_prepare / plan_apply. This path requires OPENAI_API_KEY and
    calls GPT-4o directly.
    """
    from openai import OpenAI

    project_path = Path(project_path)
    config = load_config(project_path)

    if pdf_text is None:
        pdf_path = project_path / "spec.pdf"
        if not pdf_path.exists():
            pdf_path = project_path / "slide_deck.pdf"
        pdf_text = extract_pdf_text(pdf_path)

    prompt_file = project_path / "prompt.txt"
    creative_prompt = prompt_file.read_text() if prompt_file.exists() else ""
    images = list_images(project_path)

    user_message = (
        f"# Creative Direction\n{creative_prompt}\n\n"
        f"# Available Images\n{json.dumps(images)}\n\n"
        f"# Spec Content\n{pdf_text}"
    )
    system = (
        "You are a documentary planner. Given a technical spec and creative "
        "direction, break the content into documentary chapters.\n\n"
        "Return ONLY valid JSON matching the schema below.\n\n"
        + PLAN_SCHEMA_PROMPT
    )

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
        response_format={"type": "json_object"},
    )
    plan_text = response.choices[0].message.content
    return plan_apply(project_path, plan_text)
