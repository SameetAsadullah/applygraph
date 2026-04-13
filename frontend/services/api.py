"""Backend request helpers for the Streamlit frontend."""
from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any
from urllib.parse import urljoin

import httpx


DEFAULT_API_BASE_URL = "http://localhost:8000"


def _api_url(path: str) -> str:
    return urljoin(f"{DEFAULT_API_BASE_URL}/", path.lstrip("/"))


def create_session(title: str | None = None) -> dict[str, Any]:
    response = httpx.post(_api_url("/sessions"), json={"title": title}, timeout=30.0)
    response.raise_for_status()
    return response.json()


def list_sessions() -> list[dict[str, Any]]:
    response = httpx.get(_api_url("/sessions"), timeout=30.0)
    response.raise_for_status()
    return response.json()


def get_session(session_id: str) -> dict[str, Any]:
    response = httpx.get(_api_url(f"/sessions/{session_id}"), timeout=30.0)
    response.raise_for_status()
    return response.json()


def save_session_resume(
    session_id: str,
    *,
    filename: str,
    text: str,
    page_count: int,
    char_count: int,
) -> dict[str, Any]:
    response = httpx.patch(
        _api_url(f"/sessions/{session_id}/resume"),
        json={
            "filename": filename,
            "text": text,
            "page_count": page_count,
            "char_count": char_count,
        },
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()


def delete_session(session_id: str) -> None:
    response = httpx.delete(_api_url(f"/sessions/{session_id}"), timeout=30.0)
    response.raise_for_status()


def submit_message_feedback(session_id: str, message_id: str, rating: str) -> dict[str, Any]:
    response = httpx.post(
        _api_url(f"/sessions/{session_id}/messages/{message_id}/feedback"),
        json={"rating": rating},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


def stream_chat_request(
    session_id: str,
    user_prompt: str,
) -> Iterator[dict[str, Any]]:
    payload: dict[str, Any] = {
        "session_id": session_id,
        "message": user_prompt.strip(),
    }

    with httpx.stream(
        "POST",
        _api_url("/chat/stream"),
        json=payload,
        headers={"Accept": "text/event-stream"},
        timeout=120.0,
    ) as response:
        response.raise_for_status()
        data_lines: list[str] = []
        for line in response.iter_lines():
            if line == "":
                if data_lines:
                    yield json.loads("\n".join(data_lines))
                    data_lines.clear()
                continue
            if line.startswith("data:"):
                data_lines.append(line[5:].strip())
        if data_lines:
            yield json.loads("\n".join(data_lines))
