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
        user_request: str | None = None,
    ) -> JobAnalysisResponse:
        job_skill_set = {skill.lower() for skill in job_skills if skill}
        profile_skill_set = {skill.lower() for skill in profile_skills if skill}
        matched = sorted({s for s in job_skill_set if s in profile_skill_set})
        missing = sorted(job_skill_set - profile_skill_set)

        memory_summary = "\n".join(
            f"- {snippet.memory_type.value}: {snippet.content[:200]}" for snippet in retrieved_memory
        )
        system_prompt = (
            "You are a senior job search strategist. "
            "Assess fit conservatively, ground every claim in the provided job description or candidate profile, "
            "and never invent missing experience. Write clear, specific output that a chat UI can render directly."
        )
        user_prompt = (
            f"Original user request:\n{user_request or 'N/A'}\n\n"
            f"Job description:\n{job_description[:3000] or 'N/A'}\n\n"
            f"Candidate profile:\n{candidate_profile or 'N/A'}\n\n"
            f"Matched skills: {matched}\n"
            f"Missing skills: {missing}\n"
            f"Memory context:\n{memory_summary or 'None'}\n\n"
            "Task:\n"
            "Write a crisp fit summary in 3-5 sentences (max 120 words).\n"
            "Focus on strongest overlaps, biggest risks, and one practical next step.\n"
            "Do not use bullet points, headings, or markdown."
        )
        fit_summary = await self._llm.complete(system_prompt, user_prompt)

        rec_prompt = (
            "Now list exactly 3 concrete resume changes.\n"
            "Rules:\n"
            "- each line must start with '- '\n"
            "- each recommendation must be specific to the job description\n"
            "- do not repeat the fit summary\n"
            "- do not add any intro or closing text"
        )
        rec_text = await self._llm.complete(system_prompt, user_prompt + "\n" + rec_prompt)
        recommendations = self._extract_lines(rec_text)

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

    def _extract_lines(self, text: str) -> list[str]:
        lines: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("- "):
                lines.append(line[2:].strip())
            elif line[:2].isdigit() and ". " in line:
                lines.append(line.split(". ", 1)[1].strip())
        return lines
