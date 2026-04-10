"""Tool for semantic memory retrieval."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.schemas.api import MemorySnippet
from backend.services.memory import MemoryService
from backend.tools.base import BaseTool


class MemoryRetrievalTool(BaseTool):
    def __init__(self, memory_service: MemoryService) -> None:
        super().__init__(name="memory_retriever", description="Fetch semantic memories relevant to the query")
        self._memory_service = memory_service

    async def run(
        self,
        *,
        session: AsyncSession | None,
        session_id: uuid.UUID | None,
        query_text: str,
        limit: int = 5,
    ) -> list[MemorySnippet]:
        if session is None:
            return []
        return await self._memory_service.fetch_similar(
            session,
            session_id=session_id,
            query_text=query_text,
            limit=limit,
        )
