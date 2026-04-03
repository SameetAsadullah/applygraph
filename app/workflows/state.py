"""Workflow shared state definitions."""
from __future__ import annotations

import enum
import uuid
from typing import Any, Optional, TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.api import MemorySnippet


class RequestType(str, enum.Enum):
    CHAT = "chat"
    ANALYZE_JOB = "analyze_job"
    TAILOR_RESUME = "tailor_resume"
    DRAFT_MESSAGE = "draft_message"
    SAVE_MEMORY = "save_memory"


class WorkflowState(TypedDict, total=False):
    request_type: RequestType
    user_id: Optional[uuid.UUID]
    job_description: str
    company_name: Optional[str]
    candidate_profile: Optional[str]
    resume_bullets: list[str]
    role: Optional[str]
    tone: Optional[str]
    hiring_manager_name: Optional[str]
    memory_payload: dict[str, Any]
    chat_message: Optional[str]
    chat_plan: dict[str, Any]

    db_session: AsyncSession

    parsed_job: dict[str, Any]
    parsed_profile: dict[str, Any]
    retrieved_memory: list[MemorySnippet]
    output: dict[str, Any]
    errors: list[str]
    saved_memory_ids: list[uuid.UUID]
