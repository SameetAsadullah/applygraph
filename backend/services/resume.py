"""Resume tailoring logic."""
from __future__ import annotations

from backend.schemas.api import MemorySnippet, ResumeTailorResponse
from backend.services.llm import LLMService


class ResumeTailorService:
    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    async def tailor(
        self,
        job_description: str,
        resume_bullets: list[str],
        candidate_profile: str | None,
        retrieved_memory: list[MemorySnippet],
    ) -> ResumeTailorResponse:
        memory_context = "\n".join(
            f"- {snippet.memory_type.value}: {snippet.content[:200]}" for snippet in retrieved_memory
        )
        system_prompt = "You are a staff-level recruiter rewriting resume bullets with proof over fluff."
        bullet_block = "\n".join(f"- {bullet}" for bullet in resume_bullets)
        user_prompt = (
            f"Job description: {job_description[:2000]}\n"
            f"Candidate profile: {candidate_profile or 'N/A'}\n"
            f"Past bullets:\n{bullet_block}\n"
            f"Memory context:\n{memory_context or 'None'}\n"
            "Rewrite each bullet with job-specific phrasing, keep quantifiable details, output one bullet per line."
        )
        response = await self._llm.complete(system_prompt, user_prompt)
        tailored = [line.strip('- ').strip() for line in response.splitlines() if line.strip()]
        rationale_prompt = (
            "Explain in <=3 sentences how these bullets were tailored compared to the job needs."
        )
        rationale = await self._llm.complete(system_prompt, user_prompt + "\n" + rationale_prompt)

        if not tailored:
            tailored = [bullet for bullet in resume_bullets]

        return ResumeTailorResponse(
            tailored_bullets=tailored,
            rationale=rationale.strip(),
            retrieved_memory=retrieved_memory,
        )
