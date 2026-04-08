"""Tool that drafts outreach snippets using the outreach service."""
from __future__ import annotations

from typing import Any

from backend.schemas.api import DraftMessageResponse, MemorySnippet
from backend.services.outreach import OutreachService
from backend.tools.base import BaseTool


class OutreachDraftTool(BaseTool):
    def __init__(self, outreach_service: OutreachService) -> None:
        super().__init__(name="outreach_drafter", description="Draft outreach snippets for review")
        self._service = outreach_service

    async def run(
        self,
        *,
        company: str,
        role: str,
        candidate_profile: str,
        tone: str,
        hiring_manager_name: str | None,
        outreach_format: str,
        retrieved_memory: list[MemorySnippet],
        user_request: str | None = None,
    ) -> dict[str, Any]:
        response: DraftMessageResponse = await self._service.draft(
            company=company,
            role=role,
            candidate_profile=candidate_profile,
            tone=tone,
            hiring_manager_name=hiring_manager_name,
            outreach_format=outreach_format,
            retrieved_memory=retrieved_memory,
            user_request=user_request,
        )
        return response.model_dump()
