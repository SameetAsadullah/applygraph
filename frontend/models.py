"""Typed frontend state models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChatTurn:
    role: str
    text: str
    backend_response: dict[str, Any] | None = None


@dataclass
class ResumeContext:
    filename: str = ""
    text: str = ""
    file_token: str = ""
    page_count: int = 0
    char_count: int = 0


@dataclass
class FrontendState:
    chat_turns: list[ChatTurn] = field(default_factory=list)
    resume: ResumeContext = field(default_factory=ResumeContext)
