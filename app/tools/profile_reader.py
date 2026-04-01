"""Tool for summarizing candidate profiles."""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from app.tools.base import BaseTool


class ProfileReaderTool(BaseTool):
    def __init__(self) -> None:
        super().__init__(name="profile_reader", description="Summarize profile and extract skills")

    async def run(self, profile_text: str | None) -> dict[str, Any]:
        if not profile_text:
            return {"skills": [], "summary": ""}

        tokens = re.findall(r"[A-Za-z][A-Za-z0-9+\-#]{1,20}", profile_text)
        counts = Counter(token.lower() for token in tokens)
        skills = [token for token, _ in counts.most_common(15)]
        summary = " ".join(profile_text.splitlines())[:1000]
        return {"skills": skills, "summary": summary}
