"""Session management endpoints for chat threads."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.deps import get_db_session
from backend.db.models import ChatSession
from backend.schemas.api import (
    ChatSessionCreateRequest,
    ChatSessionDetailResponse,
    ChatSessionMessageResponse,
    ChatSessionResumeRequest,
    ChatSessionSummaryResponse,
)
from backend.services.chat_sessions import ChatSessionService

router = APIRouter(prefix="/sessions", tags=["sessions"])
service = ChatSessionService()


def _require_db_session(session):
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session storage is unavailable because the database session is not configured.",
        )
    return session


def _serialize_session_summary(chat_session: ChatSession, message_count: int) -> ChatSessionSummaryResponse:
    return ChatSessionSummaryResponse(
        id=chat_session.id,
        title=chat_session.title,
        created_at=chat_session.created_at.isoformat(),
        updated_at=chat_session.updated_at.isoformat(),
        resume_filename=chat_session.resume_filename,
        message_count=message_count,
    )


def _serialize_session_detail(chat_session: ChatSession) -> ChatSessionDetailResponse:
    return ChatSessionDetailResponse(
        id=chat_session.id,
        title=chat_session.title,
        created_at=chat_session.created_at.isoformat(),
        updated_at=chat_session.updated_at.isoformat(),
        resume_filename=chat_session.resume_filename,
        resume_page_count=chat_session.resume_page_count,
        resume_char_count=chat_session.resume_char_count,
        messages=[
            ChatSessionMessageResponse(
                id=message.id,
                role=message.role,
                content=message.content,
                backend_response=message.backend_response,
                request_type=message.request_type,
                created_at=message.created_at.isoformat(),
            )
            for message in chat_session.messages
        ],
    )


@router.post("", response_model=ChatSessionDetailResponse)
async def create_session(
    payload: ChatSessionCreateRequest,
    session=Depends(get_db_session),
) -> ChatSessionDetailResponse:
    session = _require_db_session(session)
    chat_session = await service.create_session(session, title=payload.title)
    chat_session = await service.get_session(session, chat_session.id)
    assert chat_session is not None
    return _serialize_session_detail(chat_session)


@router.get("", response_model=list[ChatSessionSummaryResponse])
async def list_sessions(session=Depends(get_db_session)) -> list[ChatSessionSummaryResponse]:
    session = _require_db_session(session)
    rows = await service.list_sessions(session)
    return [_serialize_session_summary(chat_session, message_count) for chat_session, message_count in rows]


@router.get("/{session_id}", response_model=ChatSessionDetailResponse)
async def get_session(session_id: uuid.UUID, session=Depends(get_db_session)) -> ChatSessionDetailResponse:
    session = _require_db_session(session)
    chat_session = await service.get_session(session, session_id)
    if chat_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    return _serialize_session_detail(chat_session)


@router.patch("/{session_id}/resume", response_model=ChatSessionDetailResponse)
async def update_resume(
    session_id: uuid.UUID,
    payload: ChatSessionResumeRequest,
    session=Depends(get_db_session),
) -> ChatSessionDetailResponse:
    session = _require_db_session(session)
    chat_session = await service.get_session(session, session_id)
    if chat_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    updated = await service.update_resume(
        session,
        chat_session=chat_session,
        filename=payload.filename,
        text=payload.text,
        page_count=payload.page_count,
        char_count=payload.char_count,
    )
    refreshed = await service.get_session(session, updated.id)
    assert refreshed is not None
    return _serialize_session_detail(refreshed)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: uuid.UUID, session=Depends(get_db_session)) -> None:
    session = _require_db_session(session)
    chat_session = await service.get_session(session, session_id)
    if chat_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    await service.delete_session(session, chat_session=chat_session)
