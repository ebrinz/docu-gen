"""viz_extract — PDF → build/pdf_data.json with content-hash caching."""
import json
from pathlib import Path
from unittest.mock import patch

from docugen.tools.viz_extract import (
    compute_pdf_hash, viz_extract,
)


def test_compute_hash_stable(tmp_path):
    p = tmp_path / "a.pdf"
    p.write_bytes(b"fake pdf")
    h1 = compute_pdf_hash([p])
    h2 = compute_pdf_hash([p])
    assert h1 == h2 and len(h1) == 16


def test_compute_hash_changes_with_content(tmp_path):
    p = tmp_path / "a.pdf"
    p.write_bytes(b"one")
    h1 = compute_pdf_hash([p])
    p.write_bytes(b"two")
    h2 = compute_pdf_hash([p])
    assert h1 != h2


def test_viz_extract_no_pdfs(tmp_path):
    """Empty project directory (no spec.pdf / slide_deck.pdf) returns a
    no-op message rather than raising."""
    (tmp_path / "build").mkdir()
    result = viz_extract(tmp_path)
    assert "nothing to do" in result.lower()


def test_viz_extract_skips_when_hash_matches(tmp_path):
    project = tmp_path
    (project / "spec.pdf").write_bytes(b"fake")
    build = project / "build"
    build.mkdir()
    (build / "pdf_data.json").write_text(json.dumps({"cached": True}))
    h = compute_pdf_hash([project / "spec.pdf"])
    (build / "pdf_data.json.pdfhash").write_text(h)

    result = viz_extract(project)
    assert "cached" in result.lower() or "unchanged" in result.lower()
    data = json.loads((build / "pdf_data.json").read_text())
    assert data == {"cached": True}


@patch("docugen.tools.viz_extract._extract_via_vision")
@patch("docugen.tools.viz_extract.pdf_to_page_images")
def test_viz_extract_runs_when_hash_differs(mock_rasterize, mock_extract, tmp_path):
    mock_rasterize.return_value = [tmp_path / "fakepage.png"]
    mock_extract.return_value = {"page_1": {"candidate_primitive": "bar_chart"}}
    project = tmp_path
    (project / "spec.pdf").write_bytes(b"fake")
    (project / "build").mkdir()

    result = viz_extract(project)
    assert mock_extract.called
    data = json.loads((project / "build" / "pdf_data.json").read_text())
    assert data == {"page_1": {"candidate_primitive": "bar_chart"}}
    hash_file = project / "build" / "pdf_data.json.pdfhash"
    assert hash_file.exists()
    assert result.startswith("viz_extract: extracted")
