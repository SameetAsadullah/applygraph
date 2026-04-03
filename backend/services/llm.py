"""LLM utilities with graceful degradation when API keys are absent."""
from __future__ import annotations

import asyncio
import time
from typing import Optional

try:  # pragma: no cover - optional dependency guard
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover
    ChatOpenAI = None
    HumanMessage = None
    SystemMessage = None

try:  # pragma: no cover - optional dependency guard
    import google.generativeai as genai
except ImportError:  # pragma: no cover
    genai = None

from backend.core.config import Settings
from backend.telemetry.metrics import record_llm_call
from backend.telemetry.tracing import get_tracer


class LLMService:
    """Wrapper around the configured chat model with deterministic fallbacks."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._provider = (settings.llm_provider or "openai").lower()
        self._model_name = settings.llm_model
        self._client: Optional[ChatOpenAI] = None
        self._gemini_model = None

        if self._provider == "openai" and settings.openai_api_key and ChatOpenAI is not None:
            self._client = ChatOpenAI(
                model=settings.llm_model,
                temperature=0.2,
                api_key=settings.openai_api_key,
            )
        elif (
            self._provider == "gemini"
            and settings.gemini_api_key
            and genai is not None
        ):
            genai.configure(api_key=settings.gemini_api_key)
            self._model_name = settings.gemini_model
            self._gemini_model = genai.GenerativeModel(model_name=settings.gemini_model)

        self._tracer = get_tracer()

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return model text completion with tracing."""

        with self._tracer.start_as_current_span("llm.complete") as span:
            span.set_attribute("llm.provider", self._provider)
            span.set_attribute("llm.model", self._model_name)
            span.set_attribute(
                "llm.has_client", bool(self._client or self._gemini_model)
            )
            start = time.perf_counter()
            try:
                if (
                    self._provider == "openai"
                    and self._client
                    and HumanMessage
                    and SystemMessage
                ):
                    response = await self._client.ainvoke(
                        [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
                    )
                    content = (
                        response.content
                        if isinstance(response.content, str)
                        else str(response.content)
                    )
                    tokens = self._extract_token_usage(response, system_prompt, user_prompt)
                    self._record_llm_metrics(start, tokens=tokens)
                    return content
                if self._provider == "gemini" and self._gemini_model is not None:
                    result = await self._generate_with_gemini(system_prompt, user_prompt)
                    self._record_llm_metrics(
                        start,
                        tokens=self._estimate_tokens(system_prompt, user_prompt, result),
                    )
                    return result
                fallback = self._fallback(system_prompt, user_prompt)
                self._record_llm_metrics(
                    start,
                    tokens=self._estimate_tokens(system_prompt, user_prompt, fallback),
                    status="fallback",
                )
                return fallback
            except Exception:
                self._record_llm_metrics(start, status="error")
                raise

    async def _generate_with_gemini(self, system_prompt: str, user_prompt: str) -> str:
        """Invoke Gemini models without blocking the event loop."""

        prompt = f"{system_prompt}\n\n{user_prompt}"
        loop = asyncio.get_running_loop()

        def _invoke():
            response = self._gemini_model.generate_content(prompt)
            if hasattr(response, "text") and response.text:
                return response.text
            if hasattr(response, "candidates") and response.candidates:  # pragma: no cover
                parts = []
                for candidate in response.candidates:
                    content = getattr(candidate, "content", None)
                    if not content:
                        continue
                    for part in getattr(content, "parts", []):
                        part_text = getattr(part, "text", None)
                        if part_text:
                            parts.append(part_text)
                if parts:
                    return "\n".join(parts)
            return str(response)

        return await loop.run_in_executor(None, _invoke)

    def _fallback(self, system_prompt: str, user_prompt: str) -> str:
        """Deterministic text generation using prompts themselves."""

        preview = user_prompt[:400]
        return (
            "[fallback-response]\n"
            f"provider: {self._provider}\n"
            f"model: {self._model_name}\n"
            f"system: {system_prompt[:200]}\n"
            f"user: {preview}\n"
            "This environment is running in deterministic fallback mode."
        )

    def _record_llm_metrics(
        self,
        start: float,
        *,
        tokens: Optional[int] = None,
        status: str = "success",
    ) -> None:
        duration_ms = (time.perf_counter() - start) * 1000
        record_llm_call(
            self._provider,
            self._model_name,
            duration_ms,
            tokens=tokens,
            status=status,
        )

    def _extract_token_usage(
        self,
        response: object,
        system_prompt: str,
        user_prompt: str,
    ) -> Optional[int]:
        usage = getattr(response, "usage_metadata", None)
        if isinstance(usage, dict):
            total = usage.get("total_tokens")
            if total is not None:
                return int(total)
            input_tokens = usage.get("input_tokens")
            output_tokens = usage.get("output_tokens")
            if input_tokens is not None and output_tokens is not None:
                return int(input_tokens) + int(output_tokens)
        return self._estimate_tokens(system_prompt, user_prompt, getattr(response, "content", ""))

    def _estimate_tokens(
        self,
        system_prompt: str,
        user_prompt: str,
        output_text: str,
    ) -> int:
        # Rough heuristic: assume 4 characters per token
        combined = system_prompt + user_prompt + (output_text or "")
        return max(int(len(combined) / 4), 0)
