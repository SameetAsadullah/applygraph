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
        user_request: str | None = None,
    ) -> ResumeTailorResponse:
        memory_context = "\n".join(
            f"- {snippet.memory_type.value}: {snippet.content[:200]}" for snippet in retrieved_memory
        )
        system_prompt = (
            "You are an expert resume writer for senior technical roles. "
            "Answer resume-tailoring requests using only the provided job description, candidate profile, resume bullets, "
            "and memory context. Improve alignment to the role while preserving truth, evidence, and measurable impact. "
            "Do not invent technologies, outcomes, or experience."
        )
        bullet_block = "\n".join(f"- {bullet}" for bullet in resume_bullets)
        user_prompt = (
            f"Original user request:\n{user_request or 'N/A'}\n\n"
            f"Job description:\n{job_description[:3000] or 'N/A'}\n\n"
            f"Candidate profile:\n{candidate_profile or 'N/A'}\n\n"
            f"Existing resume bullets:\n{bullet_block or 'None provided'}\n\n"
            f"Memory context:\n{memory_context or 'None'}\n\n"
            "Task:\n"
            "Answer the user's request directly.\n"
            "Rules:\n"
            "- Adapt the response to what the user actually asked for instead of forcing a fixed template\n"
            "- If rewritten bullets help, include them as bullets\n"
            "- If strategic advice helps, include concise guidance after the bullets\n"
            "- Preserve numbers and evidence where possible\n"
            "- Avoid generic adjectives and filler\n"
            "- Keep the response under 240 words"
        )
        response = (await self._llm.complete(system_prompt, user_prompt)).strip()
        if not response:
            if resume_bullets:
                response = "\n".join(f"- {bullet}" for bullet in resume_bullets)
            else:
                response = (
                    "I need stronger resume details to tailor this properly. Share 3-5 bullets with concrete scope, "
                    "technologies, and measurable results so I can align them to the job."
                )

        return ResumeTailorResponse(
            response=response,
            retrieved_memory=retrieved_memory,
        )
