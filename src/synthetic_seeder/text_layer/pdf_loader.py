"""Extract text from PDF files. Supports long documents (e.g. 200+ pages)."""

from __future__ import annotations

from pathlib import Path


def extract_text_from_pdf(path: str | Path) -> str:
    """
    Extract raw text from a PDF file using pypdf.
    Handles multi-page documents; returns concatenated text with page breaks.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Not a PDF file: {path}")

    try:
        from pypdf import PdfReader
    except ImportError as err:
        raise ImportError(
            "pypdf is required for PDF support. Install with: pip install pypdf"
        ) from err

    reader = PdfReader(str(path))
    parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def get_pdf_page_texts(path: str | Path) -> list[str]:
    """
    Extract text per page. Useful for chunking long documents by page boundaries.
    Returns list of strings, one per page (empty string for blank pages).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    try:
        from pypdf import PdfReader
    except ImportError as err:
        raise ImportError("pypdf is required for PDF support. Install with: pip install pypdf") from err

    reader = PdfReader(str(path))
    return [page.extract_text() or "" for page in reader.pages]
