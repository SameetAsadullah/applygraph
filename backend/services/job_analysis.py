"""Job gap analysis business logic."""
from __future__ import annotations

from typing import Iterable

from backend.schemas.api import JobAnalysisResponse, MemorySnippet
from backend.services.llm import LLMService


class JobAnalysisService:
    """Compute skill gaps and craft summaries."""

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    async def analyze(
        self,
        job_description: str,
        job_skills: Iterable[str],
        profile_skills: Iterable[str],
        candidate_profile: str | None,
        retrieved_memory: list[MemorySnippet],
    ) -> JobAnalysisResponse:
        job_skill_set = {skill.lower() for skill in job_skills if skill}
        profile_skill_set = {skill.lower() for skill in profile_skills if skill}
        matched = sorted({s for s in job_skill_set if s in profile_skill_set})
        missing = sorted(job_skill_set - profile_skill_set)

        memory_summary = "\n".join(
            f"- {snippet.memory_type.value}: {snippet.content[:200]}" for snippet in retrieved_memory
        )
        system_prompt = "You are a senior job coach who writes concise assessments."
        user_prompt = (
            "Job Description: "
            f"{job_description[:2000]}\n"
            f"Candidate profile: {candidate_profile or 'N/A'}\n"
            f"Matched skills: {matched}\n"
            f"Missing skills: {missing}\n"
            f"Memory context: {memory_summary or 'None'}\n"
            "Write a crisp fit summary (<=120 words)."
        )
        fit_summary = await self._llm.complete(system_prompt, user_prompt)

        rec_prompt = (
            "Given the missing skills and context above, list up to 3 resume changes as bullet lines."
        )
        rec_text = await self._llm.complete(system_prompt, user_prompt + "\n" + rec_prompt)
        recommendations = [line.strip('- ').strip() for line in rec_text.splitlines() if line.strip()]

        if not recommendations:
            recommendations = [
                "Highlight quantifiable impact for the top responsibilities.",
                "Add at least one bullet describing collaboration with cross-functional partners.",
            ]

        return JobAnalysisResponse(
            matched_skills=matched,
            missing_skills=missing,
            fit_summary=fit_summary.strip(),
            resume_recommendations=recommendations[:3],
            retrieved_memory=retrieved_memory,
        )
