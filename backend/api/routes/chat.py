"""Chat endpoint that routes requests to the appropriate workflow."""
from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_db_session, get_orchestrator
from backend.schemas.api import ChatRequest, ChatResponse
from backend.workflows.job_copilot_graph import WorkflowOrchestrator
from backend.workflows.state import RequestType

router = APIRouter(prefix="", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    payload: ChatRequest,
    orchestrator: WorkflowOrchestrator = Depends(get_orchestrator),
    session=Depends(get_db_session),
) -> ChatResponse:
    state = {
        "request_type": RequestType.CHAT,
        "chat_message": payload.message,
        "user_id": payload.user_id,
        "db_session": session,
    }
    result = await orchestrator.run(state)
    output = result.get("output")
    if output is None:
        raise HTTPException(status_code=500, detail="Chat workflow failed to produce output")
    return ChatResponse(
        request_type=result.get("request_type", RequestType.CHAT).value,
        output=output,
    )
