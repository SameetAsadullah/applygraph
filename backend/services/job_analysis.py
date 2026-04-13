"""Job analysis business logic."""
from __future__ import annotations

from backend.schemas.api import JobAnalysisResponse, MemorySnippet
from backend.services.llm import LLMService


class JobAnalysisService:
    """Answer job-analysis requests directly from the user prompt."""

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    async def analyze(
        self,
        job_description: str,
        candidate_profile: str | None,
        retrieved_memory: list[MemorySnippet],
        user_request: str | None = None,
    ) -> JobAnalysisResponse:
        memory_summary = "\n".join(
            f"- {snippet.memory_type.value}: {snippet.content[:200]}" for snippet in retrieved_memory
        )
        system_prompt = (
            "You are a senior job search strategist. "
            "Answer the user's job-related question using only the provided job description, candidate profile, "
            "and retrieved memory. Assess fit conservatively, ground every claim in the inputs, and never invent "
            "missing experience, company facts, or tools. Write naturally for a chat UI."
        )
        user_prompt = (
            f"Original user request:\n{user_request or 'N/A'}\n\n"
            f"Job description:\n{job_description[:3000] or 'N/A'}\n\n"
            f"Candidate profile:\n{candidate_profile or 'N/A'}\n\n"
            f"Memory context:\n{memory_summary or 'None'}\n\n"
            "Task:\n"
            "Answer the user's request directly.\n"
            "Rules:\n"
            "- Adapt the answer to what the user actually asked for instead of forcing a fixed template\n"
            "- If the user asks about fit, explain strengths, risks, and practical next steps\n"
            "- If the user asks for advice, keep it concrete and job-specific\n"
            "- Prefer specific technologies and responsibilities over generic words\n"
            "- If the profile is missing, be explicit about uncertainty\n"
            "- Use short paragraphs or bullets only if they help the answer\n"
            "- Keep the response under 220 words\n"
            "Response:"
        )

        response_text = (await self._llm.complete(system_prompt, user_prompt)).strip()
        if not response_text:
            response_text = (
                "The profile shows some relevant overlap, but the evidence needs to be tied more directly "
                "to the role's requirements. Focus the resume on the most relevant technologies, outcomes, "
                "and responsibilities from the job description."
            )

        return JobAnalysisResponse(
            response=response_text,
            retrieved_memory=retrieved_memory,
        )
