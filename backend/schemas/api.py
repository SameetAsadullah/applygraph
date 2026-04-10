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
    outreach_message: str | None = None
    email_version: str | None = None
    retrieved_memory: list[MemorySnippet] = Field(default_factory=list)


class ChatRequest(BaseModel):
    session_id: uuid.UUID
    message: str


class ChatSessionMessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    backend_response: dict[str, Any] | None = None
    request_type: str | None = None
    created_at: str


class ChatSessionSummaryResponse(BaseModel):
    id: uuid.UUID
    title: str
    created_at: str
    updated_at: str
    resume_filename: str | None = None
    message_count: int = 0


class ChatSessionDetailResponse(BaseModel):
    id: uuid.UUID
    title: str
    created_at: str
    updated_at: str
    resume_filename: str | None = None
    resume_page_count: int = 0
    resume_char_count: int = 0
    messages: list[ChatSessionMessageResponse] = Field(default_factory=list)


class ChatSessionCreateRequest(BaseModel):
    title: str | None = None


class ChatSessionResumeRequest(BaseModel):
    filename: str
    text: str
    page_count: int = 0
    char_count: int = 0


class HealthResponse(BaseModel):
    status: str
    version: str
