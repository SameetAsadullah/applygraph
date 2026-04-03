"""Outreach drafting logic."""
from __future__ import annotations

from backend.schemas.api import DraftMessageResponse, MemorySnippet
from backend.services.llm import LLMService


class OutreachService:
    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    async def draft(
        self,
        company: str,
        role: str,
        candidate_profile: str,
        tone: str,
        hiring_manager_name: str | None,
        retrieved_memory: list[MemorySnippet],
    ) -> DraftMessageResponse:
        memory_context = "\n".join(
            f"- {snippet.memory_type.value}: {snippet.content[:200]}" for snippet in retrieved_memory
        )
        system_prompt = "You are a thoughtful candidate writing concise, specific outreach."
        base_prompt = (
            f"Company: {company}\n"
            f"Role: {role}\n"
            f"Hiring manager: {hiring_manager_name or 'Unknown'}\n"
            f"Candidate profile: {candidate_profile}\n"
            f"Tone: {tone}\n"
            f"Memory context:\n{memory_context or 'None'}\n"
            "Produce a 3-4 sentence DM plus a slightly longer email version."
        )
        dm_text = await self._llm.complete(system_prompt, base_prompt + "\nFormat as: DM: ...")
        email_text = await self._llm.complete(
            system_prompt,
            base_prompt
            + "\nFormat as an email with greeting, body, and short close. Keep <=140 words.",
        )

        return DraftMessageResponse(
            outreach_message=dm_text.strip(),
            email_version=email_text.strip(),
            retrieved_memory=retrieved_memory,
        )
