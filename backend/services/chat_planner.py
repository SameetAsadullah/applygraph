"""Planner that maps chat prompts to workflow intents."""
from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ValidationError

from backend.db.models import MemoryType
from backend.services.llm import LLMService
from backend.workflows.state import RequestType


class ChatPlan(BaseModel):
    allowed: bool = True
    rejection_reason: str | None = None
    request_type: RequestType
    job_description: str | None = None
    resume_bullets: list[str] | None = None
    candidate_profile: str | None = None
    company_name: str | None = None
    role: str | None = None
    tone: str | None = None
    hiring_manager_name: str | None = None
    memory_payload: dict[str, Any] | None = None


class ChatPlannerService:
    """LLM-backed intent router with deterministic heuristics fallback."""

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    async def plan(self, message: str) -> ChatPlan:
        system_prompt = (
            "You are a routing agent for an Agentic Job Copilot. "
            "First, decide if the user message is about job search, resumes, outreach, or saving job-related memory. "
            "Short greetings like 'hi' or 'hello' should be allowed and treated as job-related so the assistant can respond politely. "
            "If the message is off-topic, set allowed=false and provide a short rejection_reason explaining that you only handle job-application topics. "
            "If allowed=true, decide which workflow to run and extract structured arguments."
        )
        user_prompt = (
            "Possible workflows when allowed: analyze_job, tailor_resume, draft_message, save_memory.\n"
            "Return a valid JSON object with keys:\n"
            "allowed (boolean), rejection_reason (string or null), request_type (one of the workflows or 'rejected' when allowed=false), "
            "job_description, resume_bullets (array of strings), "
            "candidate_profile, company_name, role, tone, hiring_manager_name, memory_payload (object or null).\n"
            "Only fill fields that have clear data.\n"
            f"User message:\n{message}\n"
            "JSON:"
        )
        response = await self._llm.complete(system_prompt, user_prompt)
        plan_payload = self._extract_plan_payload(response, message)
        try:
            plan_obj = ChatPlan(**plan_payload)
        except ValidationError:
            # As a final fallback, force analyze_job with the raw message
            return ChatPlan(request_type=RequestType.ANALYZE_JOB, job_description=message)
        if not plan_obj.allowed and plan_obj.request_type != RequestType.REJECTED:
            plan_obj = plan_obj.model_copy(update={"request_type": RequestType.REJECTED})
        return plan_obj

    def _extract_plan_payload(self, response_text: str, original_message: str) -> dict[str, Any]:
        json_payload = self._extract_json(response_text)
        if json_payload:
            return json_payload
        return self._heuristic_plan(original_message)

    def _extract_json(self, text: str) -> dict[str, Any] | None:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    def _heuristic_plan(self, message: str) -> dict[str, Any]:
        lower = message.lower()
        stripped = message.strip()
        if self._is_simple_greeting(stripped.lower()):
            return {
                "allowed": True,
                "request_type": RequestType.ANALYZE_JOB,
                "job_description": "",
                "candidate_profile": "",
            }
        if not self._looks_job_related(lower):
            return {
                "allowed": False,
                "rejection_reason": "I can only help with job searches, resumes, outreach, or saving related notes.",
                "request_type": RequestType.REJECTED,
            }
        if "resume" in lower or "bullet" in lower:
            return {
                "allowed": True,
                "request_type": RequestType.TAILOR_RESUME,
                "job_description": self._extract_section(message, "job") or message,
                "resume_bullets": self._extract_bullets(message),
                "candidate_profile": self._extract_section(message, "profile"),
            }
        if any(keyword in lower for keyword in ["outreach", "email", "message", "dm"]):
            return {
                "allowed": True,
                "request_type": RequestType.DRAFT_MESSAGE,
                "company_name": self._extract_section(message, "company") or "Unknown company",
                "role": self._extract_section(message, "role") or "Role",
                "candidate_profile": self._extract_section(message, "profile") or message,
                "tone": self._extract_section(message, "tone") or "warm",
                "hiring_manager_name": self._extract_section(message, "hiring manager"),
            }
        if "save memory" in lower or "remember" in lower:
            content = self._extract_section(message, "content") or message
            return {
                "allowed": True,
                "request_type": RequestType.SAVE_MEMORY,
                "memory_payload": {
                    "memory_type": MemoryType.COMPANY_NOTES,
                    "content": content,
                    "metadata": {},
                },
            }
        # Default to analyze job
        return {
            "allowed": True,
            "request_type": RequestType.ANALYZE_JOB,
            "job_description": self._extract_section(message, "job") or message,
            "candidate_profile": self._extract_section(message, "profile"),
        }

    def _extract_section(self, text: str, label: str) -> str | None:
        pattern = re.compile(rf"{label}\s*:(.+)", re.IGNORECASE)
        match = pattern.search(text)
        if not match:
            return None
        value = match.group(1).strip()
        return value if value else None

    def _extract_bullets(self, text: str) -> list[str]:
        bullets = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("- ", "* ")):
                bullets.append(stripped[2:].strip())
        return bullets

    def _is_simple_greeting(self, lower_text: str) -> bool:
        greetings = {"hi", "hello", "hey", "hi!", "hello!", "hey!"}
        normalized = lower_text.strip("!. ")
        return normalized in greetings

    def _looks_job_related(self, lower_text: str) -> bool:
        keywords = [
            "job",
            "role",
            "resume",
            "cv",
            "cover letter",
            "application",
            "interview",
            "offer",
            "career",
            "hiring",
            "candidate",
            "manager",
            "company",
            "outreach",
            "message",
            "dm",
            "memory",
            "notes",
            "tailor",
            "draft",
        ]
        return any(keyword in lower_text for keyword in keywords)
