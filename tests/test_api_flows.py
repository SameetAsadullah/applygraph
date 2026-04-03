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
        "user_id": str(uuid.uuid4()),
        "message": message,
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["request_type"] == "analyze_job"
    assert "matched_skills" in data["output"]
    assert "resume_recommendations" in data["output"]


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
        "user_id": str(uuid.uuid4()),
        "message": message,
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["request_type"] == "tailor_resume"
    assert len(data["output"]["tailored_bullets"]) >= 1
    assert "rationale" in data["output"]


def test_chat_draft_message_flow(client: TestClient) -> None:
    message = (
        "Draft an outreach message.\n"
        "Company: Acme Corp\n"
        "Role: Senior Backend Engineer\n"
        "Profile: I lead backend teams shipping ML-powered experiences.\n"
        "Tone: warm"
    )
    payload = {
        "user_id": str(uuid.uuid4()),
        "message": message,
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["request_type"] == "draft_message"
    assert "outreach_message" in data["output"]
    assert "email_version" in data["output"]


def test_chat_guardrail_rejects_off_topic(client: TestClient) -> None:
    payload = {
        "user_id": str(uuid.uuid4()),
        "message": "Tell me how to bake sourdough bread.",
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["request_type"] == "rejected"
    assert "job" in data["output"]["message"].lower()


def test_chat_stream_emits_stage_events_and_final_payload(client: TestClient) -> None:
    payload = {
        "user_id": str(uuid.uuid4()),
        "message": (
            "Analyze this role.\n"
            "Job: Build FastAPI APIs and mentor engineers.\n"
            "Profile: Built Python APIs and coached backend teams."
        ),
    }
    response = client.post("/chat/stream", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse_payloads(response.text)
    assert any(event["type"] == "stage" and event["stage"] == "prepare_request" for event in events)
    final_events = [event for event in events if event["type"] == "final"]
    assert len(final_events) == 1
    assert final_events[0]["data"]["request_type"] == "analyze_job"
    assert "matched_skills" in final_events[0]["data"]["output"]
