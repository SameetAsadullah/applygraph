"""Typed frontend state models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChatTurn:
    role: str
    text: str
    id: str = ""
    backend_response: dict[str, Any] | None = None
    feedback_rating: str | None = None


@dataclass
class ResumeContext:
    filename: str = ""
    text: str = ""
    file_token: str = ""
    page_count: int = 0
    char_count: int = 0


@dataclass
class SessionSummary:
    id: str
    title: str
    updated_at: str = ""
    created_at: str = ""
    resume_filename: str = ""
    message_count: int = 0


@dataclass
class ChatSessionState:
    id: str
    title: str
    created_at: str = ""
    updated_at: str = ""
    chat_turns: list[ChatTurn] = field(default_factory=list)
    resume: ResumeContext = field(default_factory=ResumeContext)


@dataclass
class FrontendState:
    sessions: list[SessionSummary] = field(default_factory=list)
    active_session: ChatSessionState | None = None
    initialized: bool = False
