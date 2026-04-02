"""LLM utilities with graceful degradation when API keys are absent."""
from __future__ import annotations

import asyncio
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

from app.core.config import Settings
from app.telemetry.tracing import get_tracer


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
            if self._provider == "openai" and self._client and HumanMessage and SystemMessage:
                response = await self._client.ainvoke(
                    [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
                )
                return response.content if isinstance(response.content, str) else str(response.content)
            if self._provider == "gemini" and self._gemini_model is not None:
                return await self._generate_with_gemini(system_prompt, user_prompt)
            return self._fallback(system_prompt, user_prompt)

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
