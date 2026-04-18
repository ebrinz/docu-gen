"""Tests for plan_apply short-emotive ban."""
import json
import pytest
from docugen.tools.plan import _validate_short_emotive, plan_apply


def _mk_chapter(cid, narration, exaggeration=None):
    ch = {
        "id": cid,
        "title": cid.title(),
        "narration": narration,
        "scene_type": "manim",
        "images": [],
        "duration_estimate": 10.0,
    }
    if exaggeration is not None:
        ch["exaggeration"] = exaggeration
    return ch


def test_long_emotive_is_allowed():
    plan = {
        "title": "T",
        "chapters": [
            _mk_chapter("intro", "This is a nice long emotive phrase that Chatterbox handles fine.", exaggeration=0.7),
            _mk_chapter("outro", "Another long one to close.", exaggeration=0.5),
        ],
    }
    assert _validate_short_emotive(plan) == []


def test_short_hot_clip_is_rejected():
    plan = {
        "title": "T",
        "chapters": [
            _mk_chapter("intro", "Wow!", exaggeration=0.6),
            _mk_chapter("outro", "A full sentence that closes out the piece nicely.", exaggeration=0.4),
        ],
    }
    errors = _validate_short_emotive(plan)
    assert len(errors) == 1
    assert "intro" in errors[0]
    assert "1 word" in errors[0] or "1-word" in errors[0]


def test_short_clip_at_low_exaggeration_is_allowed():
    plan = {
        "title": "T",
        "chapters": [
            _mk_chapter("intro", "Yes.", exaggeration=0.1),
            _mk_chapter("outro", "Full sentence goes here as the closer.", exaggeration=0.3),
        ],
    }
    assert _validate_short_emotive(plan) == []


def test_multiple_violations_all_reported():
    plan = {
        "title": "T",
        "chapters": [
            _mk_chapter("intro", "Wow!", exaggeration=0.6),
            _mk_chapter("ch1", "Full sentence.", exaggeration=0.3),
            _mk_chapter("outro", "Yes!", exaggeration=0.5),
        ],
    }
    errors = _validate_short_emotive(plan)
    assert len(errors) == 2


def test_plan_apply_refuses_short_hot_plan(tmp_path):
    (tmp_path / "build").mkdir()
    (tmp_path / "config.yaml").write_text("title: T\n")
    plan = {
        "title": "T",
        "chapters": [
            _mk_chapter("intro", "Wow!", exaggeration=0.6),
            _mk_chapter("outro", "Full closing sentence.", exaggeration=0.3),
        ],
    }
    result = plan_apply(tmp_path, json.dumps(plan))
    assert "short-emotive ban" in result.lower() or "short + emotive" in result.lower()
    assert not (tmp_path / "build" / "plan.json").exists()
