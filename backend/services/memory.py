"""Semantic memory persistence helpers."""
from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import models
from backend.deps.embeddings import EmbeddingClient
from backend.schemas.api import MemorySnippet
from backend.telemetry.tracing import get_tracer


class MemoryService:
    def __init__(self, embedding_client: EmbeddingClient) -> None:
        self._embeddings = embedding_client
        self._tracer = get_tracer()

    async def save_memory(
        self,
        session: AsyncSession,
        *,
        session_id: uuid.UUID,
        memory_type: models.MemoryType,
        content: str,
        metadata: dict | None = None,
    ) -> models.SessionMemoryChunk:
        embedding = await self._embeddings.embed_text(content)
        chunk = models.SessionMemoryChunk(
            session_id=session_id,
            memory_type=memory_type,
            content=content,
            meta=metadata or {},
            embedding=embedding,
        )
        session.add(chunk)
        await session.commit()
        await session.refresh(chunk)
        return chunk

    async def fetch_similar(
        self,
        session: AsyncSession,
        *,
        session_id: uuid.UUID | None,
        query_text: str,
        limit: int = 5,
    ) -> list[MemorySnippet]:
        if not session_id:
            return []

        with self._tracer.start_as_current_span("memory.fetch_similar") as span:
            span.set_attribute("memory.limit", limit)
            embedding = await self._embeddings.embed_text(query_text)
            stmt = (
                select(models.SessionMemoryChunk)
                .where(models.SessionMemoryChunk.session_id == session_id)
                .order_by(models.SessionMemoryChunk.embedding.cosine_distance(embedding))
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows: Sequence[models.SessionMemoryChunk] = result.scalars().all()
            snippets = [
                MemorySnippet(
                    id=row.id,
                    memory_type=row.memory_type,
                    content=row.content,
                    metadata=row.meta or {},
                )
                for row in rows
            ]
            return snippets

    async def log_interaction(
        self,
        session: AsyncSession,
        *,
        session_id: uuid.UUID | None,
        workflow: str,
        input_summary: str,
        output_summary: str,
        trace_id: str | None,
    ) -> models.InteractionRun:
        run = models.InteractionRun(
            user_id=session_id,
            workflow=workflow,
            input_summary=input_summary[:1000],
            output_summary=output_summary[:2000],
            trace_id=trace_id,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run
