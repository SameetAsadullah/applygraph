"""LangGraph workflow for Agentic Job Copilot."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, StateGraph
from opentelemetry import trace

from app.db.models import MemoryType
from app.schemas.api import JobAnalysisResponse, ResumeTailorResponse
from app.services.job_analysis import JobAnalysisService
from app.services.memory import MemoryService
from app.services.resume import ResumeTailorService
from app.services.llm import LLMService
from app.tools.job_parser import JobParserTool
from app.tools.memory_retriever import MemoryRetrievalTool
from app.tools.outreach_drafter import OutreachDraftTool
from app.tools.profile_reader import ProfileReaderTool
from app.workflows.state import RequestType, WorkflowState


@dataclass
class WorkflowServices:
    job_parser: JobParserTool
    profile_reader: ProfileReaderTool
    memory_retriever: MemoryRetrievalTool
    job_analysis: JobAnalysisService
    resume_tailor: ResumeTailorService
    outreach_tool: OutreachDraftTool
    memory_service: MemoryService
    llm_service: LLMService


def build_workflow(services: WorkflowServices):
    graph = StateGraph(WorkflowState)
    tracer = trace.get_tracer("agentic-job-copilot.workflow")

    async def parse_input(state: WorkflowState) -> dict[str, Any]:
        job_description = state.get("job_description", "")
        profile_text = state.get("candidate_profile")
        parsed_job = await services.job_parser(job_description=job_description)
        parsed_profile = await services.profile_reader(profile_text=profile_text)
        return {"parsed_job": parsed_job, "parsed_profile": parsed_profile}

    async def classify_request(state: WorkflowState) -> dict[str, Any]:
        request_type = state.get("request_type")
        if request_type is None:
            raise ValueError("request_type is required")
        return {"request_type": request_type}

    async def retrieve_memory(state: WorkflowState) -> dict[str, Any]:
        session = state.get("db_session")
        user_id = state.get("user_id")
        query = state.get("job_description") or state.get("candidate_profile") or ""
        memories = await services.memory_retriever(
            session=session,
            user_id=user_id,
            query_text=query,
            limit=5,
        )
        return {"retrieved_memory": memories}

    async def plan_response(state: WorkflowState) -> dict[str, Any]:
        request_type = state["request_type"]
        summary_prompt = (
            f"Plan how to handle request type {request_type.value} with the inputs provided."
        )
        job_description = state.get("job_description", "")[:800]
        plan = await services.llm_service.complete(
            "You plan workflows for job application copilots.",
            f"Inputs: {job_description}\nExisting plan: {state.get('plan', '')}\n{summary_prompt}",
        )
        return {"plan": plan}

    async def generate_output(state: WorkflowState) -> dict[str, Any]:
        request_type = state["request_type"]
        retrieved_memory = state.get("retrieved_memory", [])
        if request_type == RequestType.ANALYZE_JOB:
            response: JobAnalysisResponse = await services.job_analysis.analyze(
                job_description=state.get("job_description", ""),
                job_skills=state.get("parsed_job", {}).get("skills", []),
                profile_skills=state.get("parsed_profile", {}).get("skills", []),
                candidate_profile=state.get("candidate_profile"),
                retrieved_memory=retrieved_memory,
            )
            return {"output": response.model_dump()}
        if request_type == RequestType.TAILOR_RESUME:
            response: ResumeTailorResponse = await services.resume_tailor.tailor(
                job_description=state.get("job_description", ""),
                resume_bullets=state.get("resume_bullets", []),
                candidate_profile=state.get("candidate_profile"),
                retrieved_memory=retrieved_memory,
            )
            return {"output": response.model_dump()}
        if request_type == RequestType.DRAFT_MESSAGE:
            result = await services.outreach_tool(
                company=state.get("company_name") or state.get("role") or "Company",
                role=state.get("role") or state.get("company_name") or "Role",
                candidate_profile=state.get("candidate_profile") or "",
                tone=state.get("tone") or "warm",
                hiring_manager_name=state.get("hiring_manager_name"),
                retrieved_memory=retrieved_memory,
            )
            return {"output": result}
        if request_type == RequestType.SAVE_MEMORY:
            payload = state.get("memory_payload", {})
            return {"output": payload}
        raise ValueError(f"Unsupported request type {request_type}")

    async def review_output(state: WorkflowState) -> dict[str, Any]:
        output = state.get("output")
        if not output:
            return {"errors": ["Workflow produced no output"]}
        return {}

    async def persist_memory(state: WorkflowState) -> dict[str, Any]:
        session = state.get("db_session")
        user_id = state.get("user_id")
        saved_ids = list(state.get("saved_memory_ids", []))
        if not session or not user_id:
            return {"saved_memory_ids": saved_ids}
        request_type = state["request_type"]
        payloads = []
        if request_type == RequestType.ANALYZE_JOB:
            payloads.append(
                (
                    MemoryType.JOB_DESCRIPTION,
                    state.get("job_description", ""),
                    {"company": state.get("company_name"), "skills": state.get("parsed_job", {}).get("skills", [])},
                )
            )
        elif request_type == RequestType.TAILOR_RESUME:
            payloads.append(
                (
                    MemoryType.RESUME_BULLETS,
                    "\n".join(state.get("output", {}).get("tailored_bullets", [])),
                    {"job_description": state.get("job_description")},
                )
            )
        elif request_type == RequestType.DRAFT_MESSAGE:
            payloads.append(
                (
                    MemoryType.OUTREACH,
                    state.get("output", {}).get("outreach_message", ""),
                    {"company": state.get("company_name"), "role": state.get("role")},
                )
            )
        elif request_type == RequestType.SAVE_MEMORY:
            payload = state.get("memory_payload", {})
            payloads.append(
                (
                    payload.get("memory_type", MemoryType.COMPANY_NOTES),
                    payload.get("content", ""),
                    payload.get("metadata"),
                )
            )
        for memory_type, content, metadata in payloads:
            if content:
                chunk = await services.memory_service.save_memory(
                    session,
                    user_id=user_id,
                    memory_type=memory_type,
                    content=content,
                    metadata=metadata,
                )
                saved_ids.append(chunk.id)
        return {"saved_memory_ids": saved_ids}

    async def return_result(state: WorkflowState) -> dict[str, Any]:
        span = tracer.start_span("workflow.return_result")
        span.end()
        return state

    graph.add_node("parse_input", parse_input)
    graph.add_node("classify_request", classify_request)
    graph.add_node("retrieve_memory", retrieve_memory)
    graph.add_node("plan_response", plan_response)
    graph.add_node("generate_output", generate_output)
    graph.add_node("review_output", review_output)
    graph.add_node("persist_memory", persist_memory)
    graph.add_node("return_result", return_result)

    graph.set_entry_point("parse_input")
    graph.add_edge("parse_input", "classify_request")
    graph.add_edge("classify_request", "retrieve_memory")
    graph.add_edge("retrieve_memory", "plan_response")
    graph.add_edge("plan_response", "generate_output")
    graph.add_edge("generate_output", "review_output")
    graph.add_edge("review_output", "persist_memory")
    graph.add_edge("persist_memory", "return_result")
    graph.add_edge("return_result", END)

    return graph.compile()


class WorkflowOrchestrator:
    """Thin wrapper around the compiled LangGraph workflow."""

    def __init__(self, services: WorkflowServices) -> None:
        self._graph = build_workflow(services)

    async def run(self, state: WorkflowState) -> WorkflowState:
        return await self._graph.ainvoke(state)
