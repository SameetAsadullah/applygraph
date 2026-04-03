"""Resume PDF extraction helpers."""
from __future__ import annotations

import io

from pypdf import PdfReader


def extract_resume_text(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        normalized = " ".join(text.split())
        if normalized:
            pages.append(normalized)
    return "\n\n".join(pages).strip()
