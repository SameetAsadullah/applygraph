"""Chat endpoint that routes requests to the appropriate workflow."""
from __future__ import annotations

import json
import uuid
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from backend.api.deps import get_db_session, get_orchestrator
from backend.schemas.api import ChatRequest
from backend.services.chat_sessions import ChatSessionService
from backend.workflows.job_copilot_graph import WorkflowOrchestrator
from backend.workflows.state import RequestType

router = APIRouter(prefix="", tags=["chat"])
session_service = ChatSessionService()


def _build_workflow_state(
    payload: ChatRequest,
    session: Any,
    *,
    resume_text: str | None = None,
) -> dict[str, Any]:
    return {
        "request_type": RequestType.CHAT,
        "chat_message": payload.message,
        "session_id": payload.session_id,
        "candidate_profile": resume_text,
        "db_session": session,
    }


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, uuid.UUID):
        return str(value)
    return str(value)


def _format_sse(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data, default=_json_default)}\n\n"


def _assistant_message_text(payload: dict[str, Any]) -> str:
    request_type = payload.get("request_type")
    output = payload.get("output", {})
    if request_type == "rejected":
        return output.get("message", "")
    if request_type == "analyze_job":
        return output.get("response", "")
    if request_type == "tailor_resume":
        return output.get("response", "")
    if request_type == "draft_message":
        return output.get("email_version") or output.get("outreach_message") or ""
    return json.dumps(output, default=_json_default)

@router.post("/chat/stream")
async def chat_stream_endpoint(
    payload: ChatRequest,
    orchestrator: WorkflowOrchestrator = Depends(get_orchestrator),
    session=Depends(get_db_session),
) -> StreamingResponse:
    chat_session = None
    if session is not None:
        chat_session = await session_service.get_session(session, payload.session_id)
        if chat_session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    state = _build_workflow_state(
        payload,
        session,
        resume_text=chat_session.resume_text if chat_session and chat_session.resume_text else None,
    )

    async def event_stream():
        try:
            if session is not None and chat_session is not None:
                await session_service.add_message(
                    session,
                    chat_session=chat_session,
                    role="user",
                    content=payload.message,
                )
                await session_service.maybe_autotitle(
                    session,
                    chat_session=chat_session,
                    prompt=payload.message,
                )
            async for event in orchestrator.run_stream(state):
                if (
                    event.get("type") == "final"
                    and session is not None
                    and chat_session is not None
                ):
                    final_payload = event.get("data", {})
                    await session_service.add_message(
                        session,
                        chat_session=chat_session,
                        role="assistant",
                        content=_assistant_message_text(final_payload),
                        backend_response=final_payload,
                        request_type=final_payload.get("request_type"),
                    )
                yield _format_sse(event)
        except Exception as exc:
            yield _format_sse(
                {
                    "type": "error",
                    "message": f"Chat workflow failed: {exc}",
                }
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
