"""Request/response schemas for Agentic Job Copilot APIs."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.db.models import MemoryType


class MemorySnippet(BaseModel):
    id: uuid.UUID
    memory_type: MemoryType
    content: str
    metadata: Optional[dict[str, Any]] = None


class JobAnalysisRequest(BaseModel):
    user_id: Optional[uuid.UUID] = Field(default=None, description="Known user id for personalization")
    job_description: str
    company_name: Optional[str] = None
    candidate_profile: Optional[str] = None


class JobAnalysisResponse(BaseModel):
    matched_skills: list[str]
    missing_skills: list[str]
    fit_summary: str
    resume_recommendations: list[str]
    retrieved_memory: list[MemorySnippet] = Field(default_factory=list)


class ResumeTailorRequest(BaseModel):
    user_id: Optional[uuid.UUID] = None
    job_description: str
    resume_bullets: list[str]
    candidate_profile: Optional[str] = None


class ResumeTailorResponse(BaseModel):
    tailored_bullets: list[str]
    rationale: str
    retrieved_memory: list[MemorySnippet] = Field(default_factory=list)


class DraftMessageRequest(BaseModel):
    user_id: Optional[uuid.UUID] = None
    company: str
    role: str
    hiring_manager_name: Optional[str] = None
    candidate_profile: str
    tone: str = Field(default="warm")


class DraftMessageResponse(BaseModel):
    outreach_message: str
    email_version: str
    retrieved_memory: list[MemorySnippet] = Field(default_factory=list)


class MemorySaveRequest(BaseModel):
    user_id: uuid.UUID
    memory_type: MemoryType
    content: str
    metadata: Optional[dict[str, Any]] = None


class MemorySaveResponse(BaseModel):
    status: str
    memory_id: uuid.UUID


class HealthResponse(BaseModel):
    status: str
    version: str
