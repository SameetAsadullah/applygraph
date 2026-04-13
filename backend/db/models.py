"""SQLAlchemy models for Agentic Job Copilot."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class MemoryType(str, enum.Enum):
    JOB_DESCRIPTION = "job_description"
    RESUME_BULLETS = "resume_bullets"
    OUTREACH = "outreach"
    COMPANY_NOTES = "company_notes"


class FeedbackRating(str, enum.Enum):
    UP = "up"
    DOWN = "down"


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="New chat")
    resume_filename: Mapped[str | None] = mapped_column(String(255))
    resume_text: Mapped[str | None] = mapped_column(Text)
    resume_page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resume_char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    messages: Mapped[list["ChatSessionMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatSessionMessage.created_at",
    )
    memories: Mapped[list["SessionMemoryChunk"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class ChatSessionMessage(Base):
    __tablename__ = "chat_session_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    backend_response: Mapped[dict | None] = mapped_column(JSON)
    request_type: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")
    feedback: Mapped["ChatMessageFeedback | None"] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        uselist=False,
    )


class ChatMessageFeedback(Base):
    __tablename__ = "chat_message_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_session_messages.id"),
        nullable=False,
        unique=True,
    )
    rating: Mapped[FeedbackRating] = mapped_column(Enum(FeedbackRating, name="feedback_rating_enum"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    message: Mapped["ChatSessionMessage"] = relationship(back_populates="feedback")


class SessionMemoryChunk(Base):
    __tablename__ = "session_memory_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id"),
        nullable=False,
    )
    memory_type: Mapped[MemoryType] = mapped_column(Enum(MemoryType, name="session_memory_type_enum"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict | None] = mapped_column("metadata", JSON)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    session: Mapped["ChatSession"] = relationship(back_populates="memories")
