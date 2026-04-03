"""Chat endpoint that routes requests to the appropriate workflow."""
from __future__ import annotations

import json
import uuid
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from backend.api.deps import get_db_session, get_orchestrator
from backend.schemas.api import ChatRequest
from backend.workflows.job_copilot_graph import WorkflowOrchestrator
from backend.workflows.state import RequestType

router = APIRouter(prefix="", tags=["chat"])


def _build_workflow_state(payload: ChatRequest, session: Any) -> dict[str, Any]:
    return {
        "request_type": RequestType.CHAT,
        "chat_message": payload.message,
        "user_id": payload.user_id,
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

@router.post("/chat/stream")
async def chat_stream_endpoint(
    payload: ChatRequest,
    orchestrator: WorkflowOrchestrator = Depends(get_orchestrator),
    session=Depends(get_db_session),
) -> StreamingResponse:
    state = _build_workflow_state(payload, session)

    async def event_stream():
        try:
            async for event in orchestrator.run_stream(state):
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
