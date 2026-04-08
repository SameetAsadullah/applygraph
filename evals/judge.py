from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from backend.core.config import get_settings
from backend.services.llm import LLMService


@dataclass
class JudgeResult:
    available: bool
    score: float | None
    passed: bool | None
    summary: str
    raw_response: str | None = None


class EvalJudge:
    def __init__(self) -> None:
        settings = get_settings()
        self._llm = LLMService(settings)
        self._enabled = bool(settings.openai_api_key or settings.gemini_api_key)

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def score_case(
        self,
        *,
        case_name: str,
        message: str,
        rubric: str,
        output: dict[str, Any],
    ) -> JudgeResult:
        if not self._enabled:
            return JudgeResult(
                available=False,
                score=None,
                passed=None,
                summary="LLM judge skipped because no API key is configured.",
            )

        system_prompt = (
            "You are an evaluation judge for an AI job copilot. "
            "Return only valid JSON with keys score, passed, and summary. "
            "score must be an integer from 1 to 5. passed must be true or false."
        )
        user_prompt = (
            f"Case: {case_name}\n"
            f"User prompt:\n{message}\n\n"
            f"Rubric:\n{rubric}\n\n"
            f"Assistant output JSON:\n{json.dumps(output, ensure_ascii=True)}\n\n"
            "Judge whether the output satisfies the rubric, avoids hallucinations, and routes correctly."
        )
        raw = await self._llm.complete(system_prompt, user_prompt)
        parsed = self._parse_judge_response(raw)
        if parsed is None:
            return JudgeResult(
                available=False,
                score=None,
                passed=None,
                summary="LLM judge returned unparsable output.",
                raw_response=raw,
            )
        return JudgeResult(
            available=True,
            score=float(parsed["score"]),
            passed=bool(parsed["passed"]),
            summary=str(parsed["summary"]),
            raw_response=raw,
        )

    def _parse_judge_response(self, text: str) -> dict[str, Any] | None:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
        score = payload.get("score")
        passed = payload.get("passed")
        summary = payload.get("summary")
        if not isinstance(score, int):
            return None
        if not isinstance(passed, bool):
            return None
        if not isinstance(summary, str):
            return None
        return payload
