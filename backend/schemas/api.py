"""Request/response schemas for Agentic Job Copilot APIs."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field

from backend.db.models import MemoryType


class MemorySnippet(BaseModel):
    id: uuid.UUID
    memory_type: MemoryType
    content: str
    metadata: Optional[dict[str, Any]] = None


class JobAnalysisResponse(BaseModel):
    matched_skills: list[str]
    missing_skills: list[str]
    fit_summary: str
    resume_recommendations: list[str]
    retrieved_memory: list[MemorySnippet] = Field(default_factory=list)


class ResumeTailorResponse(BaseModel):
    tailored_bullets: list[str]
    rationale: str
    retrieved_memory: list[MemorySnippet] = Field(default_factory=list)


class DraftMessageResponse(BaseModel):
    outreach_message: str
    email_version: str
    retrieved_memory: list[MemorySnippet] = Field(default_factory=list)


class ChatRequest(BaseModel):
    user_id: Optional[uuid.UUID] = None
    message: str


class HealthResponse(BaseModel):
    status: str
    version: str
