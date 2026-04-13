"""Auto-choreographer: assign animation primitives based on narration content.

Reads clip text and word_times, detects visual patterns, assigns choreography.
Runs after align, before render.
"""

import json
import re
from pathlib import Path

from docugen.config import load_config

# Known compound names for dot/reveal/merge detection
COMPOUNDS = {
    "rapamycin", "resveratrol", "spermidine", "curcumin", "berberine",
    "metformin", "pi-103", "xestospongin", "ginsenoside", "aerothionin",
    "avarol", "digitoxigenin", "equol", "fisetin", "torin1", "everolimus",
    "tacrolimus", "sirolimus", "mycophenolic", "terreic",
}

ORGANISMS = {
    "aplysina": "img_sponge_aplysina.jpg",
    "xestospongia": "img_sponge_barrel.png",
    "barrel sponge": "img_sponge_barrel.png",
    "dysidea": "img_sponge_dysidea.jpg",
    "ginseng": "img_ginseng_root.jpg",
    "panax": "img_ginseng_root.jpg",
    "foxglove": "img_foxglove.jpg",
    "digitalis": "img_foxglove.jpg",
    "soy": "img_soy_field.jpg",
    "soybean": "img_soy_field.jpg",
}

# Pattern: "plus X percent" or "+X%" or "X percent"
PCT_PATTERN = re.compile(r'(?:plus\s+)?(\d+(?:\.\d+)?)\s*percent|(\+\d+(?:\.\d+)?%)', re.I)
# Pattern: large numbers like "64,659" or "2,000" or "420 billion"
BIG_NUMBER = re.compile(r'\b(\d{1,3}(?:,\d{3})+|\d+\s*(?:billion|million|thousand))\b', re.I)
# Pattern: dollar amounts
MONEY = re.compile(r'\$[\d,.]+\s*(?:billion|million|per\s+\w+)?|\d+\s+dollars', re.I)
# Pattern: comparison words
COMPARISON = re.compile(r'\b(?:versus|vs|compared to|before|after|from\s+\d+\s+to)\b', re.I)
# Pattern: removal/deletion
REMOVAL = re.compile(r'\b(?:deleted?|removed?|gone|eliminated?|took\s+out)\b', re.I)
# Pattern: combination/pairing
COMBINATION = re.compile(r'\b(?:plus|combined|pairing|combination|synergy)\b', re.I)


def _detect_choreography(clip: dict) -> dict | None:
    """Detect appropriate choreography for a clip based on text content.

    Returns choreography dict {"type": ..., "params": ...} or None.
    """
    text = clip.get("text", "").strip()
    if not text:
        return None

    lower = text.lower()
    word_times = clip.get("word_times", [])

    # Already has choreography — don't override
    existing = clip.get("visuals", {}).get("choreography", {})
    if existing.get("type"):
        return None

    # Check for organism mentions → organism_reveal
    for org_key, img_file in ORGANISMS.items():
        if org_key in lower:
            return {
                "type": "organism_reveal",
                "params": {
                    "image": img_file,
                    "name": org_key.title(),
                    "compound": "",
                    "note": "",
                },
            }

    # Check for removal/deletion → remove_reveal (only if compounds mentioned)
    if REMOVAL.search(lower):
        compounds_found = [c for c in COMPOUNDS if c in lower]
        if compounds_found:
            return {
                "type": "remove_reveal",
                "params": {
                    "removed": compounds_found[0].title(),
                    "emerged": compounds_found[1].title() if len(compounds_found) > 1 else "",
                    "via": "",
                    "effect": "",
                },
            }

    # Check for combination/synergy with two compounds → dot_merge
    if COMBINATION.search(lower):
        compounds_found = [c for c in COMPOUNDS if c in lower]
        if len(compounds_found) >= 2:
            pct = PCT_PATTERN.search(text)
            effect = ""
            if pct:
                effect = f"+{pct.group(1) or pct.group(2)}%"
            return {
                "type": "dot_merge",
                "params": {
                    "dot1": compounds_found[0].title(),
                    "dot2": compounds_found[1].title(),
                    "pathways": [],
                    "result": effect,
                },
            }

    # Check for percentage → counter with the percentage
    pct_match = PCT_PATTERN.search(text)
    if pct_match and len(text.split()) < 12:
        val = pct_match.group(1) or pct_match.group(2)
        return {
            "type": "counter",
            "params": {"to": val, "color": "gold", "label": ""},
        }

    # Check for big numbers → counter
    big_match = BIG_NUMBER.search(text)
    if big_match and len(text.split()) < 10:
        return {
            "type": "counter",
            "params": {"to": big_match.group(0), "color": "gold", "label": ""},
        }

    # Check for money → counter with gold
    money_match = MONEY.search(text)
    if money_match and len(text.split()) < 12:
        return {
            "type": "counter",
            "params": {"to": money_match.group(0), "color": "gold", "label": ""},
        }

    # Check for comparison → before_after
    if COMPARISON.search(lower):
        numbers = re.findall(r'[\d,]+(?:\.\d+)?', text)
        if len(numbers) >= 2:
            return {
                "type": "before_after",
                "params": {
                    "label": "",
                    "before": numbers[0],
                    "after": numbers[-1],
                    "color": "gold",
                },
            }

    # Check for list of items (3+ commas or semicolons) → bar_chart
    items = [s.strip() for s in re.split(r'[,;]', text) if s.strip()]
    if len(items) >= 3 and len(text.split()) < 20:
        bar_items = [f"{item}:1:glow" for item in items[:5]]
        return {
            "type": "bar_chart",
            "params": {"items": bar_items},
        }

    # Check for single compound name mentioned prominently → anchor_drop-style highlight
    compounds_found = [c for c in COMPOUNDS if c in lower]
    if compounds_found and len(text.split()) < 15:
        return {
            "type": "anchor_drop",
            "params": {
                "name": compounds_found[0].title(),
                "count": 0,
                "color": "gold",
            },
        }

    # Fallback: if text has a strong data/number focus → data_text
    if re.search(r'\d', text) and len(text.split()) < 15:
        return {
            "type": "data_text",
            "params": {"text": text},
        }

    # No match — leave as blank (theme background + ambient)
    return None


def auto_choreograph(project_path: str | Path) -> str:
    """Auto-assign choreography to clips based on narration content.

    Reads build/clips.json (should have word_times from align step).
    Updates clips.json in place. Does NOT override existing choreography.
    """
    project_path = Path(project_path)
    clips_path = project_path / "build" / "clips.json"

    if not clips_path.exists():
        raise FileNotFoundError("No clips.json found.")

    clips_data = json.loads(clips_path.read_text())
    assigned = 0
    skipped = 0

    for chapter in clips_data["chapters"]:
        for clip in chapter["clips"]:
            # Skip clips that already have choreography
            existing = clip.get("visuals", {}).get("choreography", {})
            if existing.get("type"):
                skipped += 1
                continue

            choreo = _detect_choreography(clip)
            if choreo:
                clip["visuals"]["choreography"] = choreo
                assigned += 1

    clips_path.write_text(json.dumps(clips_data, indent=2) + "\n")
    return f"Auto-choreographed {assigned} clips ({skipped} already had choreography, {82 - assigned - skipped} remain blank)."
