"""viz_extract — decode source PDFs to structured JSON via Claude vision.

Writes build/pdf_data.json alongside a .pdfhash sidecar so re-runs skip when
the PDFs haven't changed. The vision call itself is isolated behind
_extract_via_vision so tests can mock it.

Current contract: since the MCP client itself is the vision-capable model
(Claude Code), this tool does not make its own API call. It provides the
hash-cache, page rasterization, and pdf_data.json I/O. Wiring the vision
round-trip through the MCP client is a follow-up task. For v1,
_extract_via_vision raises NotImplementedError — callers populate
pdf_data.json by hand, or patch the call in tests.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def compute_pdf_hash(pdfs: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(pdfs, key=lambda x: x.name):
        h.update(p.name.encode("utf-8"))
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def pdf_to_page_images(pdf_path: Path, out_dir: Path) -> list[Path]:
    """Rasterize a PDF to per-page PNGs using pdf2image.
    Requires Poppler on PATH. Creates out_dir if missing.
    """
    try:
        from pdf2image import convert_from_path
    except ImportError as e:
        raise RuntimeError(
            "pdf2image not installed; add to deps or ensure Poppler is on PATH"
        ) from e
    out_dir.mkdir(parents=True, exist_ok=True)
    images = convert_from_path(str(pdf_path), dpi=150)
    paths: list[Path] = []
    for i, img in enumerate(images, start=1):
        out = out_dir / f"{pdf_path.stem}_page_{i:03d}.png"
        img.save(out, "PNG")
        paths.append(out)
    return paths


def _extract_via_vision(page_images: list[Path]) -> dict:
    """Call Claude vision (or equivalent) with each page image, return
    structured decoding.

    v1 stub — must be patched by callers. Will be fleshed out once the
    MCP server gains a direct vision-invocation path in a follow-up task.
    """
    raise NotImplementedError(
        "viz_extract: _extract_via_vision is not implemented in v1. "
        "Populate build/pdf_data.json by hand or patch this call in tests."
    )


def _find_pdfs(project_path: Path) -> list[Path]:
    out = []
    for name in ("spec.pdf", "slide_deck.pdf"):
        p = project_path / name
        if p.exists():
            out.append(p)
    return out


def viz_extract(project_path: str | Path) -> str:
    project_path = Path(project_path)
    build = project_path / "build"
    build.mkdir(exist_ok=True)

    pdfs = _find_pdfs(project_path)
    if not pdfs:
        return "viz_extract: no spec.pdf or slide_deck.pdf in project — nothing to do."

    pdf_hash = compute_pdf_hash(pdfs)
    data_path = build / "pdf_data.json"
    hash_path = build / "pdf_data.json.pdfhash"

    if data_path.exists() and hash_path.exists() and hash_path.read_text().strip() == pdf_hash:
        return f"viz_extract: cached (PDFs unchanged, hash={pdf_hash})"

    images_dir = build / "pdf_pages"
    images: list[Path] = []
    for pdf in pdfs:
        images.extend(pdf_to_page_images(pdf, images_dir))

    data = _extract_via_vision(images)
    data_path.write_text(json.dumps(data, indent=2) + "\n")
    hash_path.write_text(pdf_hash)
    return (
        f"viz_extract: extracted {len(data)} pages from "
        f"{len(pdfs)} PDF(s); hash={pdf_hash}"
    )
