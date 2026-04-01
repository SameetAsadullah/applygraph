"""Outreach drafting endpoint."""
from fastapi import APIRouter, Depends

from app.api.deps import get_db_session, get_orchestrator
from app.schemas.api import DraftMessageRequest, DraftMessageResponse
from app.workflows.job_copilot_graph import WorkflowOrchestrator
from app.workflows.state import RequestType

router = APIRouter(prefix="", tags=["outreach"])


@router.post("/draft-message", response_model=DraftMessageResponse)
async def draft_message(
    payload: DraftMessageRequest,
    orchestrator: WorkflowOrchestrator = Depends(get_orchestrator),
    session=Depends(get_db_session),
) -> DraftMessageResponse:
    state = {
        "request_type": RequestType.DRAFT_MESSAGE,
        "company_name": payload.company,
        "role": payload.role,
        "hiring_manager_name": payload.hiring_manager_name,
        "candidate_profile": payload.candidate_profile,
        "tone": payload.tone,
        "user_id": payload.user_id,
        "db_session": session,
    }
    result = await orchestrator.run(state)
    return DraftMessageResponse(**result["output"])
