"""Split algorithm: break chapters into clips with emotion tagging and pacing."""

import json
import re
from pathlib import Path

from docugen.config import load_config

# Snark/emotion markers
SNARK_MARKERS = [
    "honestly", "apparently", "you're welcome", "by the way",
    "personality trait", "if you think about it", "for context",
    "before anyone asks", "let that sink in", "coincidence",
    "business plan", "i suspect", "nobody designed",
]

ABBREVIATIONS = {"dr.", "mr.", "mrs.", "ms.", "jr.", "sr.", "vs.", "etc.",
                 "e.g.", "i.e.", "fig.", "no.", "vol."}


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences on '. ', '? ', '! ' boundaries."""
    # Protect abbreviations and decimals
    protected = text
    for abbr in ABBREVIATIONS:
        protected = protected.replace(abbr, abbr.replace(".", "@@DOT@@"))
    # Protect decimal numbers (e.g., "0.1", "15.2")
    protected = re.sub(r'(\d)\.(\d)', r'\1@@DOT@@\2', protected)

    # Split on sentence boundaries
    parts = re.split(r'(?<=[.!?])\s+', protected)

    # Restore protected periods
    sentences = [p.replace("@@DOT@@", ".") for p in parts if p.strip()]
    return sentences


def _tag_emotion(text: str, base_exagg: float,
                 prev_text: str = "") -> tuple[float, str]:
    """Auto-tag emotion from text patterns. Returns (exaggeration, tag)."""
    exagg = base_exagg
    tag = "neutral"
    lower = text.lower()

    # Snark markers
    for marker in SNARK_MARKERS:
        if marker in lower:
            exagg += 0.15
            tag = "wry"
            break

    # Short sentence = punchline
    word_count = len(text.split())
    if word_count < 5 and prev_text:
        prev_words = len(prev_text.split())
        if prev_words > 25:
            exagg += 0.10
            tag = "punchline"

    # Rhetorical question
    if text.strip().endswith("?") and word_count < 15:
        exagg += 0.10
        if tag == "neutral":
            tag = "wry"

    # Dramatic markers (percentages, big numbers)
    if re.search(r'\d+\s*percent|\+\d+%', lower):
        exagg += 0.05
        if tag == "neutral":
            tag = "dramatic"

    return (min(exagg, 0.8), tag)


def _assign_pacing(text: str, prev_text: str = "") -> str:
    """Assign pacing based on text patterns."""
    words = len(text.split())
    prev_words = len(prev_text.split()) if prev_text else 0

    # Short after long = breathe (punchline)
    if words < 8 and prev_words > 25:
        return "breathe"

    # Rhetorical question
    if text.strip().endswith("?"):
        return "breathe"

    # List cadence: both current and previous are short
    if words < 8 and prev_words > 0 and prev_words < 8:
        return "tight"

    return "normal"


def split_chapter(chapter: dict, default_exaggeration: float = 0.5) -> list[dict]:
    """Split a chapter into clips.

    Args:
        chapter: Chapter dict with id, title, narration, visuals.
        default_exaggeration: Base exaggeration from config or plan.

    Returns:
        List of clip dicts.
    """
    cid = chapter["id"]
    narration = chapter.get("narration", "")
    visuals = chapter.get("visuals", {})

    # Collect all assets
    assets = list(visuals.get("existing_svg", []))
    assets.extend(visuals.get("source_images", []))
    assets.extend(visuals.get("new_svg", []))
    asset_queue = list(assets)

    # Get chapter-level exaggeration if set
    base_exagg = chapter.get("exaggeration", default_exaggeration)

    sentences = _split_sentences(narration) if narration else []
    clips = []
    clip_num = 1

    # First clip: chapter card
    clips.append({
        "clip_id": f"{cid}_{clip_num:02d}",
        "text": "",
        "exaggeration": base_exagg,
        "emotion_tag": "neutral",
        "pacing": "normal",
        "visuals": {
            "type": "chapter_card",
            "assets": [],
            "direction": "",
        },
    })
    clip_num += 1

    # Detect list cadence: 3+ consecutive short sentences (< 8 words each)
    is_list = [len(s.split()) < 8 for s in sentences]
    list_run = [False] * len(sentences)
    for i in range(len(sentences)):
        if is_list[i]:
            # Check if part of a run of 3+
            run_start = i
            while run_start > 0 and is_list[run_start - 1]:
                run_start -= 1
            run_end = i
            while run_end < len(sentences) - 1 and is_list[run_end + 1]:
                run_end += 1
            if run_end - run_start + 1 >= 3:
                list_run[i] = True

    # Walk sentences, accumulate into clips
    current_text_parts = []
    current_word_count = 0
    prev_clip_text = ""

    def _flush_clip(force_pacing=None):
        nonlocal current_text_parts, current_word_count, prev_clip_text, clip_num
        if not current_text_parts:
            return
        text = " ".join(current_text_parts)
        exagg, tag = _tag_emotion(text, base_exagg, prev_clip_text)
        pacing = force_pacing or _assign_pacing(text, prev_clip_text)

        clip_assets = []
        vis_type = "blank"
        if asset_queue:
            clip_assets = [asset_queue.pop(0)]
            vis_type = "image_reveal"

        clips.append({
            "clip_id": f"{cid}_{clip_num:02d}",
            "text": text,
            "exaggeration": round(exagg, 2),
            "emotion_tag": tag,
            "pacing": pacing,
            "visuals": {
                "type": vis_type,
                "assets": clip_assets,
                "direction": "",
            },
        })
        prev_clip_text = text
        current_text_parts = []
        current_word_count = 0
        clip_num += 1

    for i, sentence in enumerate(sentences):
        s_words = len(sentence.split())

        # List cadence: each item gets its own clip
        if list_run[i]:
            if current_text_parts:
                _flush_clip()
            current_text_parts.append(sentence)
            current_word_count = s_words
            _flush_clip(force_pacing="tight")
            continue

        # Short punchline after long setup: attach but mark breathe
        if (s_words < 5 and current_text_parts and
                current_word_count >= 20 and
                current_word_count + s_words <= 45):
            current_text_parts.append(sentence)
            current_word_count += s_words
            _flush_clip(force_pacing="breathe")
            continue

        # Would adding this sentence exceed the word limit?
        if current_word_count + s_words > 35 and current_text_parts:
            _flush_clip()

        current_text_parts.append(sentence)
        current_word_count += s_words

    # Flush remaining
    _flush_clip()

    # Distribute any remaining assets to blank clips
    for clip in clips:
        if clip["visuals"]["type"] == "blank" and asset_queue:
            clip["visuals"]["assets"] = [asset_queue.pop(0)]
            clip["visuals"]["type"] = "image_reveal"

    return clips


def split_plan(project_path: str | Path) -> str:
    """Split all chapters in plan.json into clips.

    Reads build/plan.json and config.yaml.
    Writes build/clips.json.

    Returns summary string.
    """
    project_path = Path(project_path)
    config = load_config(project_path)

    plan_path = project_path / "build" / "plan.json"
    if not plan_path.exists():
        raise FileNotFoundError("No plan.json found. Run 'plan' first.")

    plan = json.loads(plan_path.read_text())
    theme_name = config.get("theme", "biopunk")

    clips_data = {
        "title": plan.get("title", "Untitled"),
        "theme": theme_name,
        "chapters": [],
    }

    total_clips = 0
    for chapter in plan.get("chapters", []):
        default_exagg = chapter.get("exaggeration", 0.5)
        clips = split_chapter(chapter, default_exaggeration=default_exagg)
        clips_data["chapters"].append({
            "id": chapter["id"],
            "title": chapter.get("title", ""),
            "clips": clips,
        })
        total_clips += len(clips)

    clips_path = project_path / "build" / "clips.json"
    clips_path.write_text(json.dumps(clips_data, indent=2) + "\n")

    return (
        f"Split {len(plan['chapters'])} chapters into {total_clips} clips.\n"
        f"Written to {clips_path}"
    )
