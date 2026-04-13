from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.main import app


def _parse_sse_payloads(body: str) -> list[dict]:
    events: list[dict] = []
    for block in body.strip().split("\n\n"):
        data_lines = [line[5:].strip() for line in block.splitlines() if line.startswith("data:")]
        if data_lines:
            events.append(json.loads("\n".join(data_lines)))
    return events


def _post_chat_stream(client: TestClient, payload: dict) -> list[dict]:
    response = client.post("/chat/stream", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    return _parse_sse_payloads(response.text)


def _final_stream_data(events: list[dict]) -> dict:
    final_events = [event for event in events if event["type"] == "final"]
    assert len(final_events) == 1
    return final_events[0]["data"]


@pytest.fixture(scope="module")
def client() -> TestClient:
    app.dependency_overrides[deps.get_db_session] = lambda: None
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


def test_chat_analyze_job_flow(client: TestClient) -> None:
    message = (
        "Analyze this job for me.\n"
        "Job: We need a Python engineer with FastAPI and SQL skills.\n"
        "Profile: Experienced backend dev skilled in FastAPI and async Python."
    )
    payload = {
        "session_id": str(uuid.uuid4()),
        "message": message,
    }
    events = _post_chat_stream(client, payload)
    data = _final_stream_data(events)
    assert data["request_type"] == "analyze_job"
    assert data["output"]["response"]


def test_chat_tailor_resume_flow(client: TestClient) -> None:
    message = (
        "Please tailor my resume.\n"
        "Job: Looking for someone to build APIs and mentor engineers.\n"
        "Bullets:\n"
        "- Built APIs in Python\n"
        "- Improved team velocity by 20%\n"
        "Profile: Led platform team shipping APIs."
    )
    payload = {
        "session_id": str(uuid.uuid4()),
        "message": message,
    }
    events = _post_chat_stream(client, payload)
    data = _final_stream_data(events)
    assert data["request_type"] == "tailor_resume"
    assert data["output"]["response"]


def test_chat_draft_message_flow(client: TestClient) -> None:
    message = (
        "Draft an outreach message.\n"
        "Company: Acme Corp\n"
        "Role: Senior Backend Engineer\n"
        "Profile: I lead backend teams shipping ML-powered experiences.\n"
        "Tone: warm"
    )
    payload = {
        "session_id": str(uuid.uuid4()),
        "message": message,
    }
    events = _post_chat_stream(client, payload)
    data = _final_stream_data(events)
    assert data["request_type"] == "draft_message"
    assert "outreach_message" in data["output"]
    assert "email_version" in data["output"]


def test_chat_draft_email_only_flow(client: TestClient) -> None:
    message = (
        "Draft an email for a recruiter.\n"
        "Company: Acme Corp\n"
        "Role: Senior Backend Engineer\n"
        "Profile: I lead backend teams shipping ML-powered experiences.\n"
        "Tone: warm"
    )
    payload = {
        "session_id": str(uuid.uuid4()),
        "message": message,
    }
    events = _post_chat_stream(client, payload)
    data = _final_stream_data(events)
    assert data["request_type"] == "draft_message"
    assert data["output"]["email_version"]
    assert data["output"]["outreach_message"] is None


def test_chat_draft_email_named_manager_flow(client: TestClient) -> None:
    payload = {
        "session_id": str(uuid.uuid4()),
        "message": "write me an email according to mail that i can use for outreaching a hiring manager named Mavrick",
    }
    events = _post_chat_stream(client, payload)
    data = _final_stream_data(events)
    assert data["request_type"] == "draft_message"
    assert data["output"]["email_version"]
    assert data["output"]["outreach_message"] is None
    assert "mavrick" in data["output"]["email_version"].lower()


def test_chat_guardrail_rejects_off_topic(client: TestClient) -> None:
    payload = {
        "session_id": str(uuid.uuid4()),
        "message": "Tell me how to bake sourdough bread.",
    }
    events = _post_chat_stream(client, payload)
    data = _final_stream_data(events)
    assert data["request_type"] == "rejected"
    assert "job" in data["output"]["message"].lower()


def test_chat_stream_emits_stage_events_and_final_payload(client: TestClient) -> None:
    payload = {
        "session_id": str(uuid.uuid4()),
        "message": (
            "Analyze this role.\n"
            "Job: Build FastAPI APIs and mentor engineers.\n"
            "Profile: Built Python APIs and coached backend teams."
        ),
    }
    events = _post_chat_stream(client, payload)
    assert any(event["type"] == "stage" and event["stage"] == "prepare_request" for event in events)
    data = _final_stream_data(events)
    assert data["request_type"] == "analyze_job"
    assert data["output"]["response"]
