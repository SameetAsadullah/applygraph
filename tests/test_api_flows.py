from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    app.dependency_overrides[deps.get_db_session] = lambda: None
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


def test_analyze_job_flow(client: TestClient) -> None:
    payload = {
        "user_id": str(uuid.uuid4()),
        "job_description": "We need a Python engineer with FastAPI and SQL skills.",
        "candidate_profile": "Experienced backend dev skilled in FastAPI and async Python.",
    }
    response = client.post("/analyze-job", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "matched_skills" in data
    assert "resume_recommendations" in data


def test_tailor_resume_flow(client: TestClient) -> None:
    payload = {
        "user_id": str(uuid.uuid4()),
        "job_description": "Looking for someone to build APIs and mentor engineers.",
        "resume_bullets": [
            "Built APIs in Python",
            "Improved team velocity by 20%",
        ],
        "candidate_profile": "Led platform team shipping APIs.",
    }
    response = client.post("/tailor-resume", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["tailored_bullets"]) >= 1
    assert "rationale" in data


def test_draft_message_flow(client: TestClient) -> None:
    payload = {
        "user_id": str(uuid.uuid4()),
        "company": "Acme Corp",
        "role": "Senior Backend Engineer",
        "candidate_profile": "I lead backend teams shipping ML-powered experiences.",
        "tone": "warm",
    }
    response = client.post("/draft-message", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "outreach_message" in data
    assert "email_version" in data
