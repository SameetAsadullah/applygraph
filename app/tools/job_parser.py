"""Tool for parsing job descriptions into structured data."""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from app.tools.base import BaseTool

_STOPWORDS = {
    "and",
    "the",
    "you",
    "with",
    "for",
    "work",
    "team",
    "will",
    "experience",
    "skills",
    "responsibilities",
    "responsibility",
    "requirements",
    "preferred",
    "an",
    "a",
    "to",
    "of",
}


class JobParserTool(BaseTool):
    def __init__(self) -> None:
        super().__init__(name="job_parser", description="Extract skills and highlights from job text")

    async def run(self, job_description: str) -> dict[str, Any]:
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9+\-#]{1,20}", job_description)
        normalized = [token.lower() for token in tokens]
        filtered = [token for token in normalized if token not in _STOPWORDS and len(token) > 2]
        counts = Counter(filtered)
        skills = [token for token, _ in counts.most_common(20)]
        highlights = " ".join(job_description.splitlines())[:2000]
        return {"skills": skills, "highlights": highlights}
