"""LangGraph workflow for Agentic Job Copilot."""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, AsyncIterator

from langgraph.graph import END, StateGraph
from opentelemetry import trace

from backend.db.models import MemoryType
from backend.schemas.api import JobAnalysisResponse, ResumeTailorResponse
from backend.services.chat_planner import ChatPlannerService
from backend.services.job_analysis import JobAnalysisService
from backend.services.memory import MemoryService
from backend.services.resume import ResumeTailorService
from backend.services.llm import LLMService
from backend.tools.memory_retriever import MemoryRetrievalTool
from backend.tools.outreach_drafter import OutreachDraftTool
from backend.telemetry.metrics import (
    increment_workflow_counter,
    record_guardrail_rejection,
    record_workflow_latency,
)
from backend.workflows.state import RequestType, WorkflowState


WORKFLOW_STAGE_ORDER = [
    "prepare_request",
    "classify_request",
    "retrieve_memory",
    "generate_output",
    "review_output",
    "persist_memory",
    "return_result",
]

WORKFLOW_STAGE_MESSAGES = {
    "prepare_request": "Routing request",
    "classify_request": "Confirming workflow",
    "retrieve_memory": "Retrieving saved context",
    "generate_output": "Generating response",
    "review_output": "Checking output",
    "persist_memory": "Saving memory",
    "return_result": "Finalizing response",
}


@dataclass
class WorkflowServices:
    chat_planner: ChatPlannerService
    memory_retriever: MemoryRetrievalTool
    job_analysis: JobAnalysisService
    resume_tailor: ResumeTailorService
    outreach_tool: OutreachDraftTool
    memory_service: MemoryService
    llm_service: LLMService


def build_workflow(services: WorkflowServices):
    graph = StateGraph(WorkflowState)
    tracer = trace.get_tracer("agentic-job-copilot.workflow")

    async def prepare_request(state: WorkflowState) -> dict[str, Any]:
        updates: dict[str, Any] = {
            "workflow_started_at": time.perf_counter(),
        }
        if state.get("request_type") != RequestType.CHAT:
            return updates
        chat_message = state.get("chat_message") or ""
        plan = await services.chat_planner.plan(chat_message)
        updates["chat_plan"] = plan.model_dump()
        if not plan.allowed:
            reason = plan.rejection_reason or "I can only help with job application topics."
            updates["request_type"] = RequestType.REJECTED
            updates["guardrail_reason"] = reason
            record_guardrail_rejection(reason)
            return updates
        updates["request_type"] = plan.request_type
        if plan.job_description is not None:
            updates["job_description"] = plan.job_description
        if plan.resume_bullets is not None:
            updates["resume_bullets"] = plan.resume_bullets
        if plan.candidate_profile is not None:
            updates["candidate_profile"] = plan.candidate_profile
        if plan.company_name is not None:
            updates["company_name"] = plan.company_name
        if plan.role is not None:
            updates["role"] = plan.role
        if plan.tone is not None:
            updates["tone"] = plan.tone
        if plan.hiring_manager_name is not None:
            updates["hiring_manager_name"] = plan.hiring_manager_name
        if plan.outreach_format is not None:
            updates["outreach_format"] = plan.outreach_format
        if plan.memory_payload is not None:
            updates["memory_payload"] = plan.memory_payload
        return updates

    async def classify_request(state: WorkflowState) -> dict[str, Any]:
        request_type = state.get("request_type")
        if request_type is None:
            raise ValueError("request_type is required")
        return {"request_type": request_type}

    async def retrieve_memory(state: WorkflowState) -> dict[str, Any]:
        request_type = state.get("request_type")
        if request_type == RequestType.REJECTED:
            return {"retrieved_memory": []}
        session = state.get("db_session")
        session_id = state.get("session_id")
        query = state.get("job_description") or state.get("candidate_profile") or ""
        memories = await services.memory_retriever(
            session=session,
            session_id=session_id,
            query_text=query,
            limit=5,
        )
        return {"retrieved_memory": memories}

    async def generate_output(state: WorkflowState) -> dict[str, Any]:
        request_type = state["request_type"]
        retrieved_memory = state.get("retrieved_memory", [])
        if request_type == RequestType.REJECTED:
            reason = state.get("guardrail_reason") or "I can only help with job application topics."
            return {"output": {"message": reason}}
        if request_type == RequestType.ANALYZE_JOB:
            response: JobAnalysisResponse = await services.job_analysis.analyze(
                job_description=state.get("job_description", ""),
                candidate_profile=state.get("candidate_profile"),
                retrieved_memory=retrieved_memory,
                user_request=state.get("chat_message"),
            )
            return {"output": response.model_dump()}
        if request_type == RequestType.TAILOR_RESUME:
            response: ResumeTailorResponse = await services.resume_tailor.tailor(
                job_description=state.get("job_description", ""),
                resume_bullets=state.get("resume_bullets", []),
                candidate_profile=state.get("candidate_profile"),
                retrieved_memory=retrieved_memory,
                user_request=state.get("chat_message"),
            )
            return {"output": response.model_dump()}
        if request_type == RequestType.DRAFT_MESSAGE:
            result = await services.outreach_tool(
                company=state.get("company_name") or "",
                role=state.get("role") or "",
                candidate_profile=state.get("candidate_profile") or "",
                tone=state.get("tone") or "warm",
                hiring_manager_name=state.get("hiring_manager_name"),
                outreach_format=state.get("outreach_format") or "both",
                retrieved_memory=retrieved_memory,
                user_request=state.get("chat_message"),
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
        request_type = state.get("request_type")
        if request_type == RequestType.REJECTED:
            return {"saved_memory_ids": state.get("saved_memory_ids", [])}
        session = state.get("db_session")
        session_id = state.get("session_id")
        saved_ids = list(state.get("saved_memory_ids", []))
        if not session or not session_id:
            return {"saved_memory_ids": saved_ids}
        request_type = state["request_type"]
        payloads = []
        if request_type == RequestType.ANALYZE_JOB:
            payloads.append(
                (
                    MemoryType.JOB_DESCRIPTION,
                    state.get("job_description", ""),
                    {
                        "company": state.get("company_name"),
                        "analysis_preview": state.get("output", {}).get("response", "")[:200],
                    },
                )
            )
        elif request_type == RequestType.TAILOR_RESUME:
            payloads.append(
                (
                    MemoryType.RESUME_BULLETS,
                    state.get("output", {}).get("response", ""),
                    {"job_description": state.get("job_description")},
                )
            )
        elif request_type == RequestType.DRAFT_MESSAGE:
            outreach_text = (
                state.get("output", {}).get("outreach_message")
                or state.get("output", {}).get("email_version", "")
            )
            payloads.append(
                (
                    MemoryType.OUTREACH,
                    outreach_text,
                    {"company": state.get("company_name"), "role": state.get("role")},
                )
            )
        elif request_type == RequestType.SAVE_MEMORY:
            payload = state.get("memory_payload", {})
            memory_type_value = payload.get("memory_type", MemoryType.COMPANY_NOTES)
            if isinstance(memory_type_value, str):
                try:
                    memory_type = MemoryType(memory_type_value)
                except ValueError:
                    memory_type = MemoryType.COMPANY_NOTES
            else:
                memory_type = memory_type_value
            payloads.append(
                (
                    memory_type,
                    payload.get("content", ""),
                    payload.get("metadata"),
                )
            )
        for memory_type, content, metadata in payloads:
            if content:
                chunk = await services.memory_service.save_memory(
                    session,
                    session_id=session_id,
                    memory_type=memory_type,
                    content=content,
                    metadata=metadata,
                )
                saved_ids.append(chunk.id)
        return {"saved_memory_ids": saved_ids}

    async def return_result(state: WorkflowState) -> dict[str, Any]:
        span = tracer.start_span("workflow.return_result")
        span.end()
        request_type = state.get("request_type", RequestType.CHAT)
        started_at = state.get("workflow_started_at")
        if started_at:
            duration_ms = (time.perf_counter() - started_at) * 1000
            record_workflow_latency(request_type.value, duration_ms)
        increment_workflow_counter(request_type.value)
        return state

    graph.add_node("prepare_request", prepare_request)
    graph.add_node("classify_request", classify_request)
    graph.add_node("retrieve_memory", retrieve_memory)
    graph.add_node("generate_output", generate_output)
    graph.add_node("review_output", review_output)
    graph.add_node("persist_memory", persist_memory)
    graph.add_node("return_result", return_result)

    graph.set_entry_point("prepare_request")
    graph.add_edge("prepare_request", "classify_request")
    graph.add_edge("classify_request", "retrieve_memory")
    graph.add_edge("retrieve_memory", "generate_output")
    graph.add_edge("generate_output", "review_output")
    graph.add_edge("review_output", "persist_memory")
    graph.add_edge("persist_memory", "return_result")
    graph.add_edge("return_result", END)

    return graph.compile()


class WorkflowOrchestrator:
    """Thin wrapper around the compiled LangGraph workflow."""

    def __init__(self, services: WorkflowServices) -> None:
        self._graph = build_workflow(services)

    async def run_stream(self, state: WorkflowState) -> AsyncIterator[dict[str, Any]]:
        next_stage_index = 0
        if WORKFLOW_STAGE_ORDER:
            first_stage = WORKFLOW_STAGE_ORDER[0]
            yield self._stage_event(first_stage, "started")

        async for chunk in self._graph.astream(state):
            if not chunk:
                continue
            stage_name, payload = next(iter(chunk.items()))
            yield self._stage_event(stage_name, "completed", payload)
            next_stage_index += 1
            if stage_name == "return_result":
                final_state = payload if isinstance(payload, dict) else {}
                output = final_state.get("output")
                if output is None:
                    raise ValueError("Chat workflow failed to produce output")
                request_type = final_state.get("request_type", RequestType.CHAT)
                request_type_value = (
                    request_type.value if isinstance(request_type, RequestType) else str(request_type)
                )
                yield {
                    "type": "final",
                    "data": {
                        "request_type": request_type_value,
                        "output": output,
                    },
                }
                break
            if next_stage_index < len(WORKFLOW_STAGE_ORDER):
                yield self._stage_event(WORKFLOW_STAGE_ORDER[next_stage_index], "started")

    def _stage_event(
        self,
        stage_name: str,
        status: str,
        payload: Any | None = None,
    ) -> dict[str, Any]:
        event: dict[str, Any] = {
            "type": "stage",
            "stage": stage_name,
            "status": status,
            "message": WORKFLOW_STAGE_MESSAGES.get(stage_name, stage_name.replace("_", " ").title()),
        }
        if payload is not None:
            meta = self._build_stage_meta(stage_name, payload)
            if meta:
                event["meta"] = meta
        return event

    def _build_stage_meta(self, stage_name: str, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {}

        if stage_name == "prepare_request":
            request_type = payload.get("request_type")
            request_type_value = (
                request_type.value if isinstance(request_type, RequestType) else request_type
            )
            meta: dict[str, Any] = {}
            if request_type_value:
                meta["request_type"] = request_type_value
            if payload.get("guardrail_reason"):
                meta["guardrail_reason"] = payload["guardrail_reason"]
            return meta

        if stage_name == "classify_request":
            request_type = payload.get("request_type")
            request_type_value = (
                request_type.value if isinstance(request_type, RequestType) else request_type
            )
            return {"request_type": request_type_value} if request_type_value else {}

        if stage_name == "retrieve_memory":
            return {"memory_count": len(payload.get("retrieved_memory", []))}

        if stage_name == "generate_output":
            output = payload.get("output", {})
            return {"keys": sorted(output.keys())}

        if stage_name == "review_output":
            return {"errors": payload.get("errors", [])} if payload.get("errors") else {}

        if stage_name == "persist_memory":
            return {"saved_memory_count": len(payload.get("saved_memory_ids", []))}

        return {}
