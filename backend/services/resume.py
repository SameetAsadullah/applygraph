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
            "Rewrite bullets to match the target job while preserving truth, evidence, and measurable impact. "
            "Do not invent technologies or outcomes that are not supported by the input."
        )
        bullet_block = "\n".join(f"- {bullet}" for bullet in resume_bullets)
        user_prompt = (
            f"Original user request:\n{user_request or 'N/A'}\n\n"
            f"Job description:\n{job_description[:3000] or 'N/A'}\n\n"
            f"Candidate profile:\n{candidate_profile or 'N/A'}\n\n"
            f"Existing resume bullets:\n{bullet_block or 'None provided'}\n\n"
            f"Memory context:\n{memory_context or 'None'}\n\n"
            "Task:\n"
            "Rewrite the resume bullets so they better match the role.\n"
            "Rules:\n"
            "- return only bullet lines\n"
            "- every line must start with '- '\n"
            "- preserve numbers and evidence where possible\n"
            "- avoid generic adjectives and filler\n"
            "- keep each bullet to one line"
        )
        response = await self._llm.complete(system_prompt, user_prompt)
        tailored = self._extract_bullets(response)
        rationale_prompt = (
            "Explain in 2-3 sentences how the bullets were tailored to the role.\n"
            "Mention which job needs were emphasized and any important gaps that remain.\n"
            "Do not use bullet points or markdown."
        )
        rationale = await self._llm.complete(system_prompt, user_prompt + "\n" + rationale_prompt)

        if not tailored:
            tailored = [bullet for bullet in resume_bullets]

        return ResumeTailorResponse(
            tailored_bullets=tailored,
            rationale=rationale.strip(),
            retrieved_memory=retrieved_memory,
        )

    def _extract_bullets(self, text: str) -> list[str]:
        bullets: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("- "):
                bullets.append(line[2:].strip())
            elif line.startswith("* "):
                bullets.append(line[2:].strip())
        return bullets
