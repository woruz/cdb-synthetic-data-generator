"""Clean and normalize SRS text before AI processing."""

from __future__ import annotations

import re


def clean_srs_text(raw: str) -> str:
    """
    Normalize SRS text extracted from PDF or other sources.
    - Collapse excessive whitespace and newlines
    - Strip leading/trailing junk
    - Preserve structure (paragraphs) where useful
    """
    if not raw or not raw.strip():
        return ""
    text = raw.strip()
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse multiple newlines to at most two (paragraph break)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse multiple spaces/tabs to single space
    text = re.sub(r"[ \t]+", " ", text)
    # Trim space at line boundaries
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(line for line in lines if line or True)  # keep blank lines between paragraphs
    # Single final newline
    return text.strip() + "\n"
