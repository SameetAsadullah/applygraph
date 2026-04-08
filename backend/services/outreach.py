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
        outreach_format: str,
        retrieved_memory: list[MemorySnippet],
        user_request: str | None = None,
    ) -> DraftMessageResponse:
        memory_context = "\n".join(
            f"- {snippet.memory_type.value}: {snippet.content[:200]}" for snippet in retrieved_memory
        )
        normalized_company = company.strip()
        normalized_role = role.strip()
        normalized_profile = candidate_profile.strip()
        normalized_manager = (hiring_manager_name or "").strip()
        system_prompt = (
            "You are a thoughtful technical candidate writing concise outreach. "
            "Keep the note specific to the company, role, and candidate background. "
            "Do not use placeholders, labels, markdown headings, or generic networking fluff. "
            "Generate exactly the requested format and never combine DM and email into the same response. "
            "If company, role, or profile details are missing, write a polished message using only the details provided. "
            "Never invent company facts, never mention an attachment, and never use bracketed placeholders like [Company Name]. "
            "If a field is missing, omit it naturally instead of inserting filler text."
        )
        base_prompt = (
            f"Original user request:\n{user_request or 'N/A'}\n\n"
            f"Company: {normalized_company or 'Not provided'}\n"
            f"Role: {normalized_role or 'Not provided'}\n"
            f"Hiring manager: {normalized_manager or 'Not provided'}\n"
            f"Candidate profile: {normalized_profile or 'Not provided'}\n"
            f"Tone: {tone}\n"
            f"Requested format: {outreach_format}\n"
            f"Memory context:\n{memory_context or 'None'}\n"
        )
        dm_text: str | None = None
        email_text: str | None = None

        if outreach_format in {"dm", "both"}:
            dm_text = await self._llm.complete(
                system_prompt,
                base_prompt
                + "\nTask: Write only the DM body in 3-4 sentences. "
                "Never include an email subject line, email signature, or email-style formatting. "
                "If a hiring manager name is provided, use it naturally; otherwise avoid guessing a name.",
            )
        if outreach_format in {"email", "both"}:
            email_text = await self._llm.complete(
                system_prompt,
                base_prompt
                + "\nTask: Write only the email text with greeting, short body, and concise close. "
                "Keep it under 140 words. "
                "If role or company are missing, do not mention them explicitly. "
                "Do not include a subject line unless the user explicitly asked for one. "
                "Never include a DM variant, LinkedIn variant, or multiple alternatives.",
            )

        return DraftMessageResponse(
            outreach_message=self._clean_message(dm_text, "dm") if dm_text else None,
            email_version=self._clean_message(email_text, "email") if email_text else None,
            retrieved_memory=retrieved_memory,
        )

    def _clean_message(self, text: str, requested_format: str) -> str:
        cleaned = text.strip()
        cleaned = cleaned.replace("```", "").strip()
        for line in cleaned.splitlines():
            stripped = line.strip()
            if stripped:
                cleaned = cleaned[cleaned.find(stripped):]
                break
        prefixes = ("DM:", "Message:", "Email:", "LinkedIn DM:", "Email Version:", "Email Outreach:")
        for prefix in prefixes:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        if requested_format == "email":
            for marker in ("\nLinkedIn DM", "\nDM:", "\nMessage:"):
                if marker in cleaned:
                    cleaned = cleaned.split(marker, 1)[0].strip()
        if requested_format == "dm":
            for marker in ("\nEmail:", "\nEmail Version:", "\nEmail Outreach", "\nSubject:"):
                if marker in cleaned:
                    cleaned = cleaned.split(marker, 1)[0].strip()
        lines = [line.rstrip() for line in cleaned.splitlines()]
        compact_lines: list[str] = []
        previous_blank = False
        for line in lines:
            is_blank = not line.strip()
            if is_blank and previous_blank:
                continue
            compact_lines.append(line)
            previous_blank = is_blank
        return "\n".join(compact_lines).strip()
