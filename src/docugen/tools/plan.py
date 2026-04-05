"""Plan tool: extract PDF text and generate chapter plan via OpenAI."""

import json
from pathlib import Path

import fitz  # PyMuPDF
from openai import OpenAI

from docugen.config import load_config

PLAN_SYSTEM_PROMPT = """\
You are a documentary planner. Given a technical spec and creative direction,
break the content into documentary chapters.

Return ONLY valid JSON matching this schema:
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
- Always start with an "intro" chapter (scene_type: "manim", no images)
- Always end with an "outro" chapter (scene_type: "manim", no images)
- Content chapters use scene_type "mixed" and reference available images
- Narration should be conversational, ~130 words per minute pace
- duration_estimate in seconds, based on narration length
- Assign images to the chapters where they're most relevant
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


def generate_plan(project_path: str | Path, pdf_text: str | None = None) -> str:
    """Generate a chapter plan from a PDF spec + prompt via OpenAI.

    Args:
        project_path: Path to the project directory.
        pdf_text: Pre-extracted PDF text. If None, extracts from spec.pdf.

    Returns:
        Path to the written plan.json file.
    """
    project_path = Path(project_path)
    config = load_config(project_path)

    if pdf_text is None:
        pdf_path = project_path / "spec.pdf"
        pdf_text = extract_pdf_text(pdf_path)

    prompt_file = project_path / "prompt.txt"
    creative_prompt = prompt_file.read_text() if prompt_file.exists() else ""

    images = list_images(project_path)

    user_message = (
        f"# Creative Direction\n{creative_prompt}\n\n"
        f"# Available Images\n{json.dumps(images)}\n\n"
        f"# Spec Content\n{pdf_text}"
    )

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": PLAN_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
        response_format={"type": "json_object"},
    )

    plan_text = response.choices[0].message.content
    plan = json.loads(plan_text)

    if "title" not in plan or not plan["title"]:
        plan["title"] = config.get("title", "Untitled Documentary")

    build_dir = project_path / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    plan_path = build_dir / "plan.json"
    plan_path.write_text(json.dumps(plan, indent=2))

    return str(plan_path)
