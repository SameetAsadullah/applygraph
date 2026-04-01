"""Resume tailoring endpoint."""
from fastapi import APIRouter, Depends

from app.api.deps import get_db_session, get_orchestrator
from app.schemas.api import ResumeTailorRequest, ResumeTailorResponse
from app.workflows.job_copilot_graph import WorkflowOrchestrator
from app.workflows.state import RequestType

router = APIRouter(prefix="", tags=["resume"])


@router.post("/tailor-resume", response_model=ResumeTailorResponse)
async def tailor_resume(
    payload: ResumeTailorRequest,
    orchestrator: WorkflowOrchestrator = Depends(get_orchestrator),
    session=Depends(get_db_session),
) -> ResumeTailorResponse:
    state = {
        "request_type": RequestType.TAILOR_RESUME,
        "job_description": payload.job_description,
        "resume_bullets": payload.resume_bullets,
        "candidate_profile": payload.candidate_profile,
        "user_id": payload.user_id,
        "db_session": session,
    }
    result = await orchestrator.run(state)
    return ResumeTailorResponse(**result["output"])
