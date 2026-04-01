"""Analyze job endpoint."""
from fastapi import APIRouter, Depends

from app.api.deps import get_db_session, get_orchestrator
from app.schemas.api import JobAnalysisRequest, JobAnalysisResponse
from app.workflows.job_copilot_graph import WorkflowOrchestrator
from app.workflows.state import RequestType

router = APIRouter(prefix="", tags=["job-analysis"])


@router.post("/analyze-job", response_model=JobAnalysisResponse)
async def analyze_job(
    payload: JobAnalysisRequest,
    orchestrator: WorkflowOrchestrator = Depends(get_orchestrator),
    session=Depends(get_db_session),
) -> JobAnalysisResponse:
    state = {
        "request_type": RequestType.ANALYZE_JOB,
        "job_description": payload.job_description,
        "company_name": payload.company_name,
        "candidate_profile": payload.candidate_profile,
        "user_id": payload.user_id,
        "db_session": session,
    }
    result = await orchestrator.run(state)
    return JobAnalysisResponse(**result["output"])
