import json
import pytest
from docugen.split import split_chapter, split_plan


def test_split_simple_chapter():
    """A short chapter with no assets becomes one chapter_card + one blank clip."""
    chapter = {
        "id": "intro",
        "title": "The Quest",
        "narration": "This is the beginning. The quest starts here.",
        "visuals": {"existing_svg": [], "source_images": []},
    }
    clips = split_chapter(chapter, default_exaggeration=0.5)
    assert len(clips) >= 2
    assert clips[0]["visuals"]["choreography"]["type"] == "chapter_card"
    assert clips[0]["clip_id"] == "intro_01"
    assert clips[1]["clip_id"] == "intro_02"


def test_split_long_narration_breaks_at_35_words():
    """Narration over 35 words gets split into multiple clips."""
    words = " ".join(["word"] * 40) + ". " + " ".join(["more"] * 40) + "."
    chapter = {
        "id": "ch1",
        "title": "Long",
        "narration": words,
        "visuals": {"existing_svg": [], "source_images": []},
    }
    clips = split_chapter(chapter, default_exaggeration=0.5)
    content_clips = [c for c in clips if c["visuals"].get("choreography", {}).get("type") != "chapter_card"]
    assert len(content_clips) >= 2
    for clip in content_clips:
        assert len(clip["text"].split()) <= 45


def test_split_assigns_assets_to_clips():
    """Assets from visuals are distributed across clips positionally."""
    chapter = {
        "id": "ch2",
        "title": "Method",
        "narration": "First point here. Second point here. Third point here.",
        "visuals": {
            "existing_svg": ["fig1.svg", "fig2.svg"],
            "source_images": [],
        },
    }
    clips = split_chapter(chapter, default_exaggeration=0.3)
    asset_clips = [c for c in clips if c["visuals"].get("content", {}).get("assets")]
    assert len(asset_clips) >= 1
    all_assets = []
    for c in asset_clips:
        all_assets.extend(c["visuals"]["content"]["assets"])
    assert "fig1.svg" in all_assets
    assert "fig2.svg" in all_assets


def test_split_emotion_tags_snark():
    """Sentences with snark markers get bumped exaggeration."""
    chapter = {
        "id": "ch3",
        "title": "Snarky",
        "narration": "This is a very long setup sentence about something technical and boring. Honestly.",
        "visuals": {"existing_svg": [], "source_images": []},
    }
    clips = split_chapter(chapter, default_exaggeration=0.2)
    content_clips = [c for c in clips if c["text"]]
    has_bump = any(c["exaggeration"] > 0.2 for c in content_clips)
    assert has_bump


def test_split_pacing_breathe_for_punchline():
    """Short sentence after long one gets 'breathe' pacing."""
    chapter = {
        "id": "ch4",
        "title": "Dramatic",
        "narration": "They tracked how many times each yeast cell divided before it died and out of two thousand compounds tested they found two that worked. Two.",
        "visuals": {"existing_svg": [], "source_images": []},
    }
    clips = split_chapter(chapter, default_exaggeration=0.3)
    punchline_clips = [c for c in clips if "Two." in c["text"]]
    assert any(c["pacing"] == "breathe" for c in punchline_clips)


def test_split_pacing_tight_for_lists():
    """Sequential short items get 'tight' pacing."""
    chapter = {
        "id": "ch5",
        "title": "Scale",
        "narration": "22,000 herbal compounds. 18,000 marine natural products. 18,000 pharmaceuticals. 900 nutraceuticals. 64,659 total.",
        "visuals": {"existing_svg": [], "source_images": []},
    }
    clips = split_chapter(chapter, default_exaggeration=0.3)
    tight_clips = [c for c in clips if c["pacing"] == "tight"]
    assert len(tight_clips) >= 1


def test_split_plan_produces_clips_json(tmp_path):
    """split_plan reads plan.json and writes clips.json."""
    plan = {
        "title": "Test",
        "chapters": [{
            "id": "intro",
            "title": "Intro",
            "narration": "Hello world.",
            "exaggeration": 0.5,
            "visuals": {"existing_svg": [], "source_images": []},
        }],
    }
    (tmp_path / "config.yaml").write_text("title: Test\ntheme: biopunk\n")
    build = tmp_path / "build"
    build.mkdir()
    (build / "plan.json").write_text(json.dumps(plan))

    result = split_plan(tmp_path)
    clips_path = build / "clips.json"
    assert clips_path.exists()
    clips_data = json.loads(clips_path.read_text())
    assert clips_data["theme"] == "biopunk"
    assert len(clips_data["chapters"]) == 1
    assert len(clips_data["chapters"][0]["clips"]) >= 1
