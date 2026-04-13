"""Persistence helpers for chat sessions and messages."""
from __future__ import annotations

import enum
import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db import models


class ChatSessionService:
    async def create_session(
        self,
        session: AsyncSession,
        *,
        title: str | None = None,
    ) -> models.ChatSession:
        chat_session = models.ChatSession(title=(title or "New chat").strip() or "New chat")
        session.add(chat_session)
        await session.commit()
        await session.refresh(chat_session)
        return chat_session

    async def list_sessions(self, session: AsyncSession) -> list[tuple[models.ChatSession, int]]:
        message_counts = (
            select(
                models.ChatSessionMessage.session_id,
                func.count(models.ChatSessionMessage.id).label("message_count"),
            )
            .group_by(models.ChatSessionMessage.session_id)
            .subquery()
        )
        stmt = (
            select(
                models.ChatSession,
                func.coalesce(message_counts.c.message_count, 0),
            )
            .outerjoin(message_counts, message_counts.c.session_id == models.ChatSession.id)
            .order_by(models.ChatSession.updated_at.desc(), models.ChatSession.created_at.desc())
        )
        result = await session.execute(stmt)
        return list(result.all())

    async def get_session(
        self,
        session: AsyncSession,
        session_id: uuid.UUID,
    ) -> models.ChatSession | None:
        stmt = (
            select(models.ChatSession)
            .options(selectinload(models.ChatSession.messages).selectinload(models.ChatSessionMessage.feedback))
            .where(models.ChatSession.id == session_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_resume(
        self,
        session: AsyncSession,
        *,
        chat_session: models.ChatSession,
        filename: str,
        text: str,
        page_count: int,
        char_count: int,
    ) -> models.ChatSession:
        chat_session.resume_filename = filename
        chat_session.resume_text = text
        chat_session.resume_page_count = page_count
        chat_session.resume_char_count = char_count
        chat_session.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(chat_session)
        return chat_session

    async def add_message(
        self,
        session: AsyncSession,
        *,
        chat_session: models.ChatSession,
        role: str,
        content: str,
        backend_response: dict | None = None,
        request_type: str | None = None,
    ) -> models.ChatSessionMessage:
        message = models.ChatSessionMessage(
            session_id=chat_session.id,
            role=role,
            content=content,
            backend_response=self._json_safe(backend_response),
            request_type=request_type,
        )
        chat_session.updated_at = datetime.utcnow()
        session.add(message)
        await session.commit()
        await session.refresh(message)
        return message

    async def maybe_autotitle(
        self,
        session: AsyncSession,
        *,
        chat_session: models.ChatSession,
        prompt: str,
    ) -> models.ChatSession:
        if (chat_session.title or "").strip().lower() != "new chat":
            return chat_session
        normalized = " ".join(prompt.split()).strip()
        if not normalized:
            return chat_session
        chat_session.title = normalized[:72]
        chat_session.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(chat_session)
        return chat_session

    async def delete_session(
        self,
        session: AsyncSession,
        *,
        chat_session: models.ChatSession,
    ) -> None:
        await session.delete(chat_session)
        await session.commit()

    async def get_message(
        self,
        session: AsyncSession,
        *,
        session_id: uuid.UUID,
        message_id: uuid.UUID,
    ) -> models.ChatSessionMessage | None:
        stmt = (
            select(models.ChatSessionMessage)
            .options(selectinload(models.ChatSessionMessage.feedback))
            .where(
                models.ChatSessionMessage.id == message_id,
                models.ChatSessionMessage.session_id == session_id,
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def set_feedback(
        self,
        session: AsyncSession,
        *,
        message: models.ChatSessionMessage,
        rating: models.FeedbackRating,
    ) -> models.ChatMessageFeedback:
        feedback = message.feedback
        if feedback is None:
            feedback = models.ChatMessageFeedback(
                message_id=message.id,
                rating=rating,
            )
            session.add(feedback)
        else:
            feedback.rating = rating
            feedback.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(feedback)
        return feedback

    def _json_safe(self, value: Any) -> Any:
        if value is None:
            return None
        return json.loads(json.dumps(value, default=self._json_default))

    def _json_default(self, value: Any) -> Any:
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, enum.Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)
