from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from backend.core.config import Settings, get_settings
from backend.services.llm import LLMService


@dataclass
class JudgeResult:
    available: bool
    score: float | None
    passed: bool | None
    summary: str
    raw_response: str | None = None


@dataclass
class JudgeConfig:
    provider: str
    model: str
    openai_api_key: str | None
    gemini_api_key: str | None

    @property
    def enabled(self) -> bool:
        provider = self.provider.lower()
        if provider == "openai":
            return bool(self.openai_api_key)
        if provider == "gemini":
            return bool(self.gemini_api_key)
        return False


def load_judge_config() -> JudgeConfig:
    base = get_settings()
    provider = os.getenv("EVAL_JUDGE_PROVIDER", base.llm_provider).lower()
    model = os.getenv(
        "EVAL_JUDGE_MODEL",
        base.llm_model if provider == "openai" else base.gemini_model,
    )
    openai_api_key = os.getenv("EVAL_JUDGE_OPENAI_API_KEY", base.openai_api_key or "")
    gemini_api_key = os.getenv("EVAL_JUDGE_GEMINI_API_KEY", base.gemini_api_key or "")
    return JudgeConfig(
        provider=provider,
        model=model,
        openai_api_key=openai_api_key or None,
        gemini_api_key=gemini_api_key or None,
    )


class EvalJudge:
    def __init__(self) -> None:
        config = load_judge_config()
        base = get_settings()
        settings = Settings(
            app_env=base.app_env,
            database_url=base.database_url,
            sync_database_url=base.sync_database_url,
            llm_provider=config.provider,
            llm_model=config.model if config.provider == "openai" else base.llm_model,
            gemini_model=config.model if config.provider == "gemini" else base.gemini_model,
            openai_api_key=config.openai_api_key,
            gemini_api_key=config.gemini_api_key,
            otel_exporter_otlp_endpoint="",
        )
        self._llm = LLMService(settings)
        self._config = config
        self._enabled = config.enabled

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
                summary=(
                    "LLM judge skipped because the configured judge provider has no API key. "
                    "Set EVAL_JUDGE_PROVIDER / EVAL_JUDGE_MODEL / EVAL_JUDGE_*_API_KEY."
                ),
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
