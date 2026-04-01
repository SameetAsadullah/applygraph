"""Embedding helpers backed by OpenAI with deterministic fallbacks."""
from __future__ import annotations

import asyncio
import hashlib
import math
from typing import Optional

try:  # pragma: no cover - optional dependency import guard
    from langchain_openai import OpenAIEmbeddings
except ImportError:  # pragma: no cover
    OpenAIEmbeddings = None

from app.core.config import Settings


class EmbeddingClient:
    """Wrap OpenAI embeddings with a hash-based fallback for offline usage."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._dim = settings.pgvector_dim
        self._client: Optional[OpenAIEmbeddings] = None
        if settings.openai_api_key and OpenAIEmbeddings is not None:
            self._client = OpenAIEmbeddings(
                model=settings.embedding_model,
                api_key=settings.openai_api_key,
            )

    async def embed_text(self, text: str) -> list[float]:
        """Return an embedding vector for the supplied text."""

        if self._client:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, lambda: self._client.embed_query(text))
        return self._hash_embed(text)

    def _hash_embed(self, text: str) -> list[float]:
        """Deterministic fallback embedding using hashed token frequencies."""

        digest = hashlib.sha256(text.encode("utf-8")).digest()
        repeats = math.ceil(self._dim / len(digest))
        tiled = (digest * repeats)[: self._dim]
        vector = [((byte / 255.0) * 2) - 1 for byte in tiled]
        return vector
