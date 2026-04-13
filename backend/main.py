"""FastAPI entrypoint for Agentic Job Copilot."""
from __future__ import annotations

import logging

from fastapi import FastAPI

from backend.api.routes import chat, health, sessions
from backend.core.config import Settings, get_settings
from backend.db.session import init_db
from backend.deps.embeddings import EmbeddingClient
from backend.services.chat_planner import ChatPlannerService
from backend.services.job_analysis import JobAnalysisService
from backend.services.llm import LLMService
from backend.services.memory import MemoryService
from backend.services.outreach import OutreachService
from backend.services.resume import ResumeTailorService
from backend.telemetry.metrics import setup_metrics
from backend.telemetry.tracing import setup_tracing
from backend.tools.memory_retriever import MemoryRetrievalTool
from backend.tools.outreach_drafter import OutreachDraftTool
from backend.workflows.job_copilot_graph import WorkflowOrchestrator, WorkflowServices


def _build_orchestrator(settings: Settings) -> WorkflowOrchestrator:
    embeddings = EmbeddingClient(settings)
    memory_service = MemoryService(embeddings)
    llm_service = LLMService(settings)
    services = WorkflowServices(
        chat_planner=ChatPlannerService(llm_service),
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
    setup_metrics(settings)

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
    app.include_router(sessions.router)
    app.include_router(chat.router)

    return app


app = create_app()
