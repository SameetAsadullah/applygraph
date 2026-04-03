"""Resume PDF extraction helpers."""
from __future__ import annotations

import io
from dataclasses import dataclass

from pypdf import PdfReader


@dataclass
class ResumeExtraction:
    text: str
    page_count: int
    char_count: int


def extract_resume_text(file_bytes: bytes) -> str:
    return extract_resume(file_bytes).text


def extract_resume(file_bytes: bytes) -> ResumeExtraction:
    reader = PdfReader(io.BytesIO(file_bytes))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        normalized = " ".join(text.split())
        if normalized:
            pages.append(normalized)
    combined = "\n\n".join(pages).strip()
    return ResumeExtraction(
        text=combined,
        page_count=len(reader.pages),
        char_count=len(combined),
    )
