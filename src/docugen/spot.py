"""Spot tool: build audio cue sheet from visual direction + timing.

Film spotting — walks every clip's cue_words, computes global timestamps,
maps events to audio spans using the slide registry's span patterns,
and writes build/cue_sheet.json for the score tool to consume.

Runs after direct_apply, before render.
"""

import json
from pathlib import Path

from docugen.themes.slides import SLIDE_REGISTRY


def _compute_global_offsets(clips_data: dict) -> dict[str, float]:
    """Compute global start time for each clip from timing model.

    Returns dict of clip_id -> global_offset_seconds.
    """
    offsets = {}
    global_offset = 0.0

    for chapter in clips_data["chapters"]:
        for clip in chapter["clips"]:
            clip_id = clip["clip_id"]
            offsets[clip_id] = global_offset
            timing = clip.get("timing", {})
            global_offset += timing.get("clip_duration", 3.0)

    return offsets


def build_cue_sheet(clips_data: dict) -> list[dict]:
    """Build the audio cue sheet from clips with visual direction.

    For each clip, looks up its slide_type's span patterns in the registry,
    resolves cue_word timestamps to global times, and emits audio spans.

    Returns list of span dicts sorted by start time.
    """
    global_offsets = _compute_global_offsets(clips_data)
    spans = []

    for chapter in clips_data["chapters"]:
        for clip in chapter["clips"]:
            clip_id = clip["clip_id"]
            clip_global = global_offsets.get(clip_id, 0.0)
            visuals = clip.get("visuals", {})
            slide_type = visuals.get("slide_type", "")
            cue_words = visuals.get("cue_words", [])
            word_times = clip.get("word_times", [])

            # Get span patterns for this slide type
            registry_entry = SLIDE_REGISTRY.get(slide_type, {})
            span_patterns = registry_entry.get("spans", [])

            if not span_patterns or not cue_words:
                continue

            # Build a lookup: event_name -> list of global timestamps
            event_times = {}
            for cue in cue_words:
                event = cue.get("event", "")
                idx = cue.get("at_index", 0)
                if idx < len(word_times):
                    local_time = word_times[idx].get("start", 0.0)
                else:
                    local_time = 0.0
                event_times.setdefault(event, []).append(local_time)

            # Resolve each span pattern against the cue_word timestamps
            for pattern in span_patterns:
                trigger = pattern["trigger"]
                if trigger not in event_times:
                    continue

                for local_time in event_times[trigger]:
                    global_time = clip_global + local_time
                    start = round(global_time + pattern["offset"], 3)
                    end = round(start + pattern["duration"], 3)

                    # Don't allow negative start times
                    if start < 0:
                        start = 0.0

                    spans.append({
                        "start": start,
                        "end": end,
                        "event": trigger,
                        "clip_id": clip_id,
                        "audio": pattern["audio"],
                        "curve": pattern["curve"],
                        "duration": round(pattern["duration"], 3),
                    })

    # Sort by start time
    spans.sort(key=lambda s: s["start"])
    return spans


def spot_project(project_path: str | Path) -> str:
    """Build and write the audio cue sheet for a project.

    Reads build/clips.json (must have visual direction + timing from direct_apply).
    Writes build/cue_sheet.json.

    Returns summary string.
    """
    project_path = Path(project_path)
    build_dir = project_path / "build"
    clips_path = build_dir / "clips.json"

    if not clips_path.exists():
        raise FileNotFoundError("No clips.json found. Run direct_apply first.")

    clips_data = json.loads(clips_path.read_text())
    spans = build_cue_sheet(clips_data)

    cue_sheet_path = build_dir / "cue_sheet.json"
    cue_sheet_path.write_text(json.dumps(spans, indent=2) + "\n")

    # Summary stats
    audio_types = {}
    for span in spans:
        audio_types[span["audio"]] = audio_types.get(span["audio"], 0) + 1

    type_summary = ", ".join(f"{v}x {k}" for k, v in sorted(audio_types.items()))
    total_dur = spans[-1]["end"] if spans else 0

    return (
        f"Cue sheet: {len(spans)} audio spans over {total_dur:.1f}s\n"
        f"Types: {type_summary}\n"
        f"Written to {cue_sheet_path}"
    )
