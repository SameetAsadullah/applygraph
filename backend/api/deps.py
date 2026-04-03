"""Shared FastAPI dependencies."""
from __future__ import annotations

from fastapi import Depends, Request

from backend.workflows.job_copilot_graph import WorkflowOrchestrator
from backend.db.session import get_session


async def get_db_session(session=Depends(get_session)):
    return session


def get_orchestrator(request: Request) -> WorkflowOrchestrator:
    orchestrator: WorkflowOrchestrator | None = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        raise RuntimeError("Workflow orchestrator is not initialized")
    return orchestrator
