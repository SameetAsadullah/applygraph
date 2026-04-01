"""Memory endpoints."""
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db_session, get_orchestrator
from app.schemas.api import MemorySaveRequest, MemorySaveResponse
from app.workflows.job_copilot_graph import WorkflowOrchestrator
from app.workflows.state import RequestType

router = APIRouter(prefix="", tags=["memory"])


@router.post("/memory/save", response_model=MemorySaveResponse)
async def save_memory(
    payload: MemorySaveRequest,
    orchestrator: WorkflowOrchestrator = Depends(get_orchestrator),
    session=Depends(get_db_session),
) -> MemorySaveResponse:
    state = {
        "request_type": RequestType.SAVE_MEMORY,
        "memory_payload": payload.model_dump(),
        "user_id": payload.user_id,
        "db_session": session,
    }
    result = await orchestrator.run(state)
    saved_ids = result.get("saved_memory_ids", [])
    if not saved_ids:
        raise HTTPException(status_code=500, detail="Memory was not persisted")
    return MemorySaveResponse(status="saved", memory_id=saved_ids[-1])
