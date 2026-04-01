"""FastAPI entrypoint for Agentic Job Copilot."""
from __future__ import annotations

import logging

from fastapi import FastAPI

from app.api.routes import analyze_job, draft_message, health, memory, tailor_resume
from app.core.config import Settings, get_settings
from app.db.session import init_db
from app.deps.embeddings import EmbeddingClient
from app.services.job_analysis import JobAnalysisService
from app.services.llm import LLMService
from app.services.memory import MemoryService
from app.services.outreach import OutreachService
from app.services.resume import ResumeTailorService
from app.telemetry.tracing import setup_tracing
from app.tools.job_parser import JobParserTool
from app.tools.memory_retriever import MemoryRetrievalTool
from app.tools.outreach_drafter import OutreachDraftTool
from app.tools.profile_reader import ProfileReaderTool
from app.workflows.job_copilot_graph import WorkflowOrchestrator, WorkflowServices


def _build_orchestrator(settings: Settings) -> WorkflowOrchestrator:
    embeddings = EmbeddingClient(settings)
    memory_service = MemoryService(embeddings)
    llm_service = LLMService(settings)
    services = WorkflowServices(
        job_parser=JobParserTool(),
        profile_reader=ProfileReaderTool(),
        memory_retriever=MemoryRetrievalTool(memory_service),
        job_analysis=JobAnalysisService(llm_service),
        resume_tailor=ResumeTailorService(llm_service),
        outreach_tool=OutreachDraftTool(OutreachService(llm_service)),
        memory_service=memory_service,
        llm_service=llm_service,
    )
    return WorkflowOrchestrator(services)


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Agentic Job Copilot", version="0.1.0")
    setup_tracing(app, settings)

    orchestrator = _build_orchestrator(settings)
    app.state.settings = settings
    app.state.orchestrator = orchestrator

    @app.on_event("startup")
    async def _startup() -> None:
        try:
            await init_db()
        except Exception as exc:  # pragma: no cover - defensive startup path
            logger.warning("Skipping DB init due to error: %s", exc)

    app.include_router(health.router)
    app.include_router(analyze_job.router)
    app.include_router(tailor_resume.router)
    app.include_router(draft_message.router)
    app.include_router(memory.router)

    return app


app = create_app()
