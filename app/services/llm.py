"""LLM utilities with graceful degradation when API keys are absent."""
from __future__ import annotations

from typing import Optional

try:  # pragma: no cover - optional dependency guard
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover
    ChatOpenAI = None
    HumanMessage = None
    SystemMessage = None

from app.core.config import Settings
from app.telemetry.tracing import get_tracer


class LLMService:
    """Wrapper around the configured chat model with deterministic fallbacks."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Optional[ChatOpenAI] = None
        if settings.openai_api_key and ChatOpenAI is not None:
            self._client = ChatOpenAI(
                model=settings.llm_model,
                temperature=0.2,
                api_key=settings.openai_api_key,
            )
        self._tracer = get_tracer()

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return model text completion with tracing."""

        with self._tracer.start_as_current_span("llm.complete") as span:
            span.set_attribute("llm.model", self.settings.llm_model)
            span.set_attribute("llm.has_client", bool(self._client))
            if self._client and HumanMessage and SystemMessage:
                response = await self._client.ainvoke(
                    [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
                )
                return response.content if isinstance(response.content, str) else str(response.content)
            return self._fallback(system_prompt, user_prompt)

    def _fallback(self, system_prompt: str, user_prompt: str) -> str:
        """Deterministic text generation using prompts themselves."""

        preview = user_prompt[:400]
        return (
            "[fallback-response]\n"
            f"system: {system_prompt[:200]}\n"
            f"user: {preview}\n"
            "This environment is running in deterministic fallback mode."
        )
