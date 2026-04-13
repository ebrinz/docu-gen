"""Align tool: cross-correlate narration text with Whisper word timestamps.

Runs Whisper on each clip WAV to get word-level timing, then aligns
Whisper's (often garbled) transcription against our known ground-truth
text using sequence alignment. Result: every word in the narration
gets a precise timestamp.
"""

import json
import re
from pathlib import Path
from difflib import SequenceMatcher

from docugen.config import load_config


def _normalize(word: str) -> str:
    """Normalize a word for fuzzy matching — lowercase, strip punctuation."""
    return re.sub(r'[^a-z0-9]', '', word.lower())


def _align_words(ground_truth: list[str], whisper_words: list[dict]) -> list[dict]:
    """Align ground-truth words to Whisper timestamps using sequence matching.

    Args:
        ground_truth: list of words from our narration text
        whisper_words: list of {"word": str, "start": float, "end": float} from Whisper

    Returns:
        list of {"word": str, "start": float, "end": float} for each ground-truth word
    """
    if not ground_truth or not whisper_words:
        return []

    gt_norm = [_normalize(w) for w in ground_truth]
    wh_norm = [_normalize(w.get("word", "")) for w in whisper_words]

    # Use SequenceMatcher to find the best alignment
    matcher = SequenceMatcher(None, gt_norm, wh_norm)
    aligned = []

    # Build a mapping: gt_index -> whisper_index
    gt_to_wh = {}
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                gt_to_wh[i1 + k] = j1 + k
        elif tag == "replace":
            # Best effort: map positionally within the replaced block
            gt_len = i2 - i1
            wh_len = j2 - j1
            for k in range(min(gt_len, wh_len)):
                gt_to_wh[i1 + k] = j1 + k

    # Assign timestamps, interpolating for unmatched words
    result = []
    for i, word in enumerate(ground_truth):
        if i in gt_to_wh:
            wh_idx = gt_to_wh[i]
            result.append({
                "word": word,
                "start": whisper_words[wh_idx]["start"],
                "end": whisper_words[wh_idx]["end"],
            })
        else:
            # Interpolate from nearest matched neighbors
            prev_time = 0.0
            next_time = whisper_words[-1]["end"] if whisper_words else 1.0

            for j in range(i - 1, -1, -1):
                if j in gt_to_wh:
                    prev_time = whisper_words[gt_to_wh[j]]["end"]
                    break
            for j in range(i + 1, len(ground_truth)):
                if j in gt_to_wh:
                    next_time = whisper_words[gt_to_wh[j]]["start"]
                    break

            # Place this word proportionally in the gap
            gap_words = 1
            gap_start = i
            for j in range(i - 1, -1, -1):
                if j in gt_to_wh:
                    gap_start = j + 1
                    break
                gap_start = j
            for j in range(gap_start, len(ground_truth)):
                if j in gt_to_wh:
                    break
                gap_words += 1

            pos_in_gap = i - gap_start
            frac = pos_in_gap / max(gap_words, 1)
            est_start = prev_time + frac * (next_time - prev_time)
            est_dur = (next_time - prev_time) / max(gap_words, 1)

            result.append({
                "word": word,
                "start": round(est_start, 3),
                "end": round(est_start + est_dur, 3),
            })

    return result


_whisper_model = None


def _get_whisper_model():
    """Lazy-load Whisper model (load once per session)."""
    global _whisper_model
    if _whisper_model is None:
        import whisper
        _whisper_model = whisper.load_model("small")
    return _whisper_model


def _whisper_transcribe(wav_path: str) -> list[dict]:
    """Run Whisper on a WAV file, return word-level timestamps."""
    model = _get_whisper_model()
    result = model.transcribe(str(wav_path), word_timestamps=True)

    words = []
    for seg in result.get("segments", []):
        for w in seg.get("words", []):
            words.append({
                "word": w["word"].strip(),
                "start": round(w["start"], 3),
                "end": round(w["end"], 3),
            })

    # Fix bunched-up timestamps: if multiple words have start=0.0,
    # spread them proportionally up to the first non-zero timestamp
    if len(words) > 1:
        first_nonzero = None
        for i, w in enumerate(words):
            if w["start"] > 0.01:
                first_nonzero = i
                break

        if first_nonzero and first_nonzero > 1:
            end_time = words[first_nonzero]["start"]
            for i in range(first_nonzero):
                frac = i / first_nonzero
                words[i]["start"] = round(frac * end_time, 3)
                words[i]["end"] = round((i + 1) / first_nonzero * end_time, 3)

    return words


def align_clip(clip_text: str, wav_path: Path) -> list[dict]:
    """Align a clip's narration text with Whisper timestamps from its WAV.

    Returns list of {"word": str, "start": float, "end": float} for each
    word in clip_text, with timestamps from the actual audio.
    """
    if not clip_text.strip() or not wav_path.exists():
        return []

    ground_truth = clip_text.split()
    whisper_words = _whisper_transcribe(wav_path)

    return _align_words(ground_truth, whisper_words)


def align_plan(project_path: str | Path) -> str:
    """Run alignment on all clips. Adds word_times to clips.json.

    Reads build/clips.json and build/narration/*.wav.
    Updates clips.json in place with word_times per clip.
    """
    project_path = Path(project_path)
    clips_path = project_path / "build" / "clips.json"
    narr_dir = project_path / "build" / "narration"

    if not clips_path.exists():
        raise FileNotFoundError("No clips.json found. Run 'split' first.")

    clips_data = json.loads(clips_path.read_text())
    aligned_count = 0
    total_words = 0

    for chapter in clips_data["chapters"]:
        for clip in chapter["clips"]:
            text = clip.get("text", "").strip()
            if not text:
                clip["word_times"] = []
                continue

            wav_path = narr_dir / f"{clip['clip_id']}.wav"
            if not wav_path.exists():
                clip["word_times"] = []
                continue

            word_times = align_clip(text, wav_path)
            clip["word_times"] = word_times
            aligned_count += 1
            total_words += len(word_times)

    clips_path.write_text(json.dumps(clips_data, indent=2) + "\n")
    return f"Aligned {aligned_count} clips, {total_words} words timestamped."


def find_word_time(word_times: list[dict], target: str) -> float | None:
    """Find the start time of a target word/phrase in aligned word_times.

    Searches for the first occurrence. Case-insensitive, handles partial matches.
    Returns start time in seconds, or None if not found.
    """
    target_lower = target.lower()
    target_words = target_lower.split()

    if len(target_words) == 1:
        # Single word search
        for wt in word_times:
            if _normalize(wt["word"]) == _normalize(target):
                return wt["start"]
        # Fuzzy fallback
        for wt in word_times:
            if _normalize(target) in _normalize(wt["word"]):
                return wt["start"]
    else:
        # Multi-word phrase search
        for i in range(len(word_times) - len(target_words) + 1):
            match = all(
                _normalize(word_times[i + j]["word"]) == _normalize(target_words[j])
                for j in range(len(target_words))
            )
            if match:
                return word_times[i]["start"]

    return None
