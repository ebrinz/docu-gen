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
