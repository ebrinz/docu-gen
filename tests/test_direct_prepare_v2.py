"""direct_prepare attaches pdf_data + primitive schemas to the context."""
import json
from docugen.direct import direct_prepare


def _scaffold(tmp_path, with_pdf_data=False):
    build = tmp_path / "build"
    build.mkdir()
    (tmp_path / "images").mkdir()
    clips = {
        "chapters": [{"id": "ch1", "title": "Intro", "clips": [
            {"clip_id": "ch1_01", "text": "hello",
             "word_times": [{"word": "hello", "start": 0, "end": 0.3}],
             "pacing": "normal"},
        ]}]
    }
    (build / "clips.json").write_text(json.dumps(clips))
    if with_pdf_data:
        (build / "pdf_data.json").write_text(json.dumps(
            {"page_1": {"candidate_primitive": "bar_chart",
                         "data": {"series": [{"label": "X", "value": 1}]}}}
        ))


def test_prepare_includes_primitive_schemas(tmp_path):
    _scaffold(tmp_path)
    out = direct_prepare(tmp_path)
    assert "callout" in out
    assert "DATA_SCHEMA" in out
    assert "Available Slide Types" in out
    assert "Primitive Data Schemas" in out


def test_prepare_includes_pdf_data_when_present(tmp_path):
    _scaffold(tmp_path, with_pdf_data=True)
    out = direct_prepare(tmp_path)
    assert "page_1" in out
    assert "bar_chart" in out


def test_prepare_no_pdf_data_gracefully(tmp_path):
    _scaffold(tmp_path, with_pdf_data=False)
    out = direct_prepare(tmp_path)
    assert "pdf_data.json" in out


def test_prepare_skips_deprecated_primitives_in_schema_block(tmp_path):
    """dot_merge and remove_reveal are DEPRECATED; their schemas should not
    be surfaced in the Primitive Data Schemas section."""
    _scaffold(tmp_path)
    out = direct_prepare(tmp_path)
    # Schemas block should not contain deprecated primitives
    schemas_idx = out.index("## Primitive Data Schemas")
    next_section = out.index("## Extracted Source Data", schemas_idx)
    schemas_block = out[schemas_idx:next_section]
    assert "### dot_merge" not in schemas_block
    assert "### remove_reveal" not in schemas_block
    # But they should still appear in the Available Slide Types list (with
    # [DEPRECATED] prefix)
    assert "DEPRECATED" in out


def test_prior_directions_included_in_per_clip_context(tmp_path):
    """Each clip's context must include summaries of preceding clips' direction."""
    from docugen.direct import prepare_direction_context

    # Minimal project with three clips; first two have direction, third doesn't
    (tmp_path / "build").mkdir()
    (tmp_path / "config.yaml").write_text("title: T\n")
    (tmp_path / "prompt.txt").write_text("prompt\n")
    (tmp_path / "build" / "plan.json").write_text('{"title":"T","chapters":[]}')

    import json
    clips = {
        "chapters": [{
            "id": "ch1",
            "clips": [
                {"clip_id": "ch1_01", "text": "a", "direction": {"slide_type": "banner_intro", "transition_in": "fade"}},
                {"clip_id": "ch1_02", "text": "b", "direction": {"slide_type": "photo_organism", "transition_in": "cut"}},
                {"clip_id": "ch1_03", "text": "c"},
            ],
        }]
    }
    (tmp_path / "build" / "clips.json").write_text(json.dumps(clips))

    ctx = prepare_direction_context(tmp_path)
    # The third clip's section must reference the first two as prior_directions
    assert "prior_directions" in ctx.lower() or "prior directions" in ctx.lower()
    # Both preceding slide_types should appear in the third clip's prior list
    ch1_03_idx = ctx.find("ch1_03")
    assert ch1_03_idx > 0
    slice_after = ctx[ch1_03_idx:ch1_03_idx + 500]
    assert "banner_intro" in slice_after
    assert "photo_organism" in slice_after
