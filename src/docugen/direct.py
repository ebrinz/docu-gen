"""Creative director: prepare context for MCP client + validate and apply results.

This module makes ZERO external API calls. The MCP client (Claude Code on Max)
does all reasoning in conversation. This module only:
1. Reads local files and formats context summaries
2. Validates direction JSON against the slide registry
3. Computes timing from WAV files + word_times
4. Writes results to clips.json
"""

import json
from pathlib import Path

from docugen.config import load_config
from docugen.timing import compute_clip_timing, get_wav_duration
from docugen.themes.slides import (
    validate_slide_type, validate_cue_event, get_slide_types_prompt,
    PRIMITIVE_ALIASES,
)
from docugen.themes.primitives import discover_primitives
from docugen.themes.primitives._base import validate_schema

REQUIRED_FIELDS = {"slide_type", "assets", "cue_words", "layout",
                   "transition_in", "transition_out", "transition_sound"}

VALID_LAYOUTS = {"center", "split_left_right", "bottom_third", "full_bleed"}
VALID_TRANSITIONS = {"crossfade", "cut", "wipe_left", "fade_black", "crossfade_next"}
THEME_SOUNDS = {
    "imperial_chime", "dark_swell", "crystal_ping", "heartbeat",
    "bell", "sonar", "resolve", "tension",
}


def validate_clip_direction(direction: dict, clip: dict,
                            available_assets: set[str]) -> list[str]:
    """Validate a single clip's visual direction. Returns list of error strings."""
    errors = []
    clip_id = clip.get("clip_id", "unknown")

    for field in REQUIRED_FIELDS:
        if field not in direction:
            errors.append(f"{clip_id}: missing required field '{field}'")

    slide_type = direction.get("slide_type", "")
    if slide_type and not validate_slide_type(slide_type):
        errors.append(f"{clip_id}: invalid slide_type '{slide_type}'")

    for asset in direction.get("assets", []):
        if asset not in available_assets:
            errors.append(f"{clip_id}: asset not found '{asset}'")

    word_times = clip.get("word_times", [])
    for cue in direction.get("cue_words", []):
        idx = cue.get("at_index", -1)
        if idx < 0 or (word_times and idx >= len(word_times)):
            errors.append(
                f"{clip_id}: cue_words at_index {idx} out of bounds "
                f"(max {len(word_times) - 1})"
            )
        event = cue.get("event", "")
        if slide_type and event and not validate_cue_event(slide_type, event):
            errors.append(
                f"{clip_id}: invalid event '{event}' for slide_type '{slide_type}'"
            )

    layout = direction.get("layout", "")
    if layout and layout not in VALID_LAYOUTS:
        errors.append(f"{clip_id}: invalid layout '{layout}'")

    for field in ("transition_in", "transition_out"):
        val = direction.get(field, "")
        if val and val not in VALID_TRANSITIONS:
            errors.append(f"{clip_id}: invalid {field} '{val}'")

    sound = direction.get("transition_sound")
    if sound is not None and sound not in THEME_SOUNDS:
        errors.append(f"{clip_id}: invalid transition_sound '{sound}'")

    # Primitive schema validation — resolves aliases first, then checks
    # clip.visuals.data against the primitive's DATA_SCHEMA.
    if slide_type:
        resolved = PRIMITIVE_ALIASES.get(slide_type, slide_type)
        primitives = discover_primitives()
        mod = primitives.get(resolved)
        if mod is not None:
            data = direction.get("data")
            if data is None:
                if mod.DATA_SCHEMA.get("required"):
                    errors.append(
                        f"{clip_id}: missing 'data' block required by "
                        f"primitive {resolved!r}"
                    )
            else:
                errors.extend(
                    validate_schema(data, mod.DATA_SCHEMA, f"{clip_id}.data")
                )

    return errors


def validate_all_clips(clips_data: dict, available_assets: set[str]) -> list[str]:
    """Validate all clips in clips_data. Returns aggregated error list."""
    all_errors = []
    for chapter in clips_data.get("chapters", []):
        for clip in chapter.get("clips", []):
            direction = clip.get("visuals", {})
            errors = validate_clip_direction(direction, clip, available_assets)
            all_errors.extend(errors)
    return all_errors


def direct_prepare(project_path: str | Path) -> str:
    """Gather context for creative direction. No API calls.

    Reads production plan, clips.json, and available assets from disk.
    Returns a formatted summary string for the MCP client to reason about.
    """
    project_path = Path(project_path)
    build_dir = project_path / "build"
    images_dir = project_path / "images"

    clips_data = json.loads((build_dir / "clips.json").read_text())
    plan_path = build_dir / "plan.json"
    production_plan = json.loads(plan_path.read_text()) if plan_path.exists() else {}

    available_assets = sorted(f.name for f in images_dir.iterdir()) if images_dir.exists() else []
    slide_types_desc = get_slide_types_prompt()

    sections = []
    for chapter in clips_data["chapters"]:
        ch_id = chapter["id"]
        ch_title = chapter.get("title", "")
        plan_chapter = next(
            (c for c in production_plan.get("chapters", []) if c["id"] == ch_id), {}
        )
        plan_visuals = plan_chapter.get("visuals", {}).get("manim", "")
        plan_svg = plan_chapter.get("visuals", {}).get("existing_svg", [])
        plan_images = plan_chapter.get("visuals", {}).get("source_images", [])

        sections.append(f"\n## Chapter: {ch_id} — {ch_title}")
        if plan_visuals:
            sections.append(f"Visual direction: {plan_visuals}")
        if plan_svg or plan_images:
            sections.append(f"Planned assets: {plan_svg + plan_images}")

        for clip in chapter["clips"]:
            cid = clip["clip_id"]
            text = clip.get("text", "(no narration)")
            n_words = len(clip.get("word_times", []))
            pacing = clip.get("pacing", "normal")
            sections.append(f"  {cid} [{n_words} words, {pacing}]: {text}")

    clips_block = "\n".join(sections)
    assets_block = "\n".join(f"  - {a}" for a in available_assets)

    return (
        f"# Creative Direction Context\n\n"
        f"## Available Slide Types\n{slide_types_desc}\n\n"
        f"## Available Assets\n{assets_block}\n\n"
        f"## Clips Needing Direction\n{clips_block}\n\n"
        f"## Output Format\n"
        f"Provide a JSON object where keys are clip_ids and values have:\n"
        f"- slide_type: one of the types above\n"
        f"- assets: list of filenames from available assets (empty if none)\n"
        f"- cue_words: list of {{\"word\": \"...\", \"at_index\": N, \"event\": \"...\", \"params\": {{}}}}\n"
        f"- layout: center | split_left_right | bottom_third | full_bleed\n"
        f"- transition_in: crossfade | cut | wipe_left | fade_black\n"
        f"- transition_out: crossfade_next | cut | fade_black\n"
        f"- transition_sound: one of the 8 theme sounds, or null\n"
    )


def recompute_timing(project_path: str | Path) -> str:
    """Recompute per-clip timing from WAV durations + word_times.

    Reads build/clips.json and build/narration/*.wav, rewrites clips.json
    with fresh timing fields. Safe to call whenever narration changes.
    """
    project_path = Path(project_path)
    build_dir = project_path / "build"
    narr_dir = build_dir / "narration"
    clips_path = build_dir / "clips.json"

    if not clips_path.exists():
        raise FileNotFoundError("No clips.json found. Run 'split' first.")

    clips_data = json.loads(clips_path.read_text())
    updated = 0
    for chapter in clips_data["chapters"]:
        offset = 0.0
        for clip in chapter["clips"]:
            wav_path = narr_dir / f"{clip['clip_id']}.wav"
            wav_dur = get_wav_duration(wav_path) if wav_path.exists() else 0.0
            clip["timing"] = compute_clip_timing(clip, wav_dur, offset)
            offset += clip["timing"]["clip_duration"]
            updated += 1

    clips_path.write_text(json.dumps(clips_data, indent=2) + "\n")
    return f"Recomputed timing for {updated} clips."


def direct_apply(project_path: str | Path, direction_json: str) -> str:
    """Apply creative direction JSON to clips.json. No API calls.

    Validates direction, computes timing from WAV files, writes clips.json.

    Args:
        project_path: Path to project directory.
        direction_json: JSON string — clip_id keys, direction object values.
    """
    project_path = Path(project_path)
    build_dir = project_path / "build"
    images_dir = project_path / "images"

    clips_data = json.loads((build_dir / "clips.json").read_text())
    available_assets = {f.name for f in images_dir.iterdir()} if images_dir.exists() else set()

    directions = json.loads(direction_json)

    applied = 0
    for chapter in clips_data["chapters"]:
        for clip in chapter["clips"]:
            clip_id = clip["clip_id"]
            if clip_id in directions:
                clip["visuals"] = directions[clip_id]
                applied += 1

    errors = validate_all_clips(clips_data, available_assets)
    if errors:
        (build_dir / "clips.json").write_text(json.dumps(clips_data, indent=2) + "\n")
        error_list = "\n".join(f"  - {e}" for e in errors)
        return (
            f"Applied direction to {applied} clips but validation found {len(errors)} errors:\n"
            f"{error_list}\n\n"
            f"clips.json updated — fix errors and re-run, or proceed to render."
        )

    (build_dir / "clips.json").write_text(json.dumps(clips_data, indent=2) + "\n")
    recompute_timing(project_path)
    return f"Directed {applied} clips. Timing computed. All validation passed. clips.json updated."
