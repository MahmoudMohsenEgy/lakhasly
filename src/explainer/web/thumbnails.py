# src/explainer/web/thumbnails.py
"""Rasterize the first page of a study PDF to a PNG for gallery thumbnails.

Uses PyMuPDF (fitz), already a project dependency. Thumbnails are cached on disk
by the caller; this module only does the PDF -> PNG rendering.
"""
from pathlib import Path

import fitz

THUMB_WIDTH = 480  # px; first page is scaled to roughly this width


def render_first_page(pdf_path: str, out_path: str, width: int = THUMB_WIDTH) -> str:
    """Render page 0 of ``pdf_path`` to a PNG at ``out_path``, scaled to ~``width`` px.

    Raises if the PDF cannot be opened or has no pages (caller maps that to a 422 so
    the gallery falls back to a placeholder)."""
    doc = fitz.open(pdf_path)
    try:
        if doc.page_count == 0:
            raise ValueError("PDF has no pages")
        page = doc.load_page(0)
        page_width = page.rect.width or width
        zoom = width / page_width
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        pix.save(out_path)
    finally:
        doc.close()
    return out_path
