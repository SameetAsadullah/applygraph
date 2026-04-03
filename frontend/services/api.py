"""Backend request helpers for the Streamlit frontend."""
from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx


DEFAULT_API_URL = "http://localhost:8000/chat"
DEFAULT_STREAM_API_URL = "http://localhost:8000/chat/stream"


def build_backend_message(user_prompt: str, resume_text: str) -> str:
    prompt = user_prompt.strip()
    profile = resume_text.strip()
    if profile:
        return f"{prompt}\n\nProfile: {profile}"
    return prompt


def submit_chat_request(
    user_prompt: str,
    resume_text: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "message": build_backend_message(user_prompt, resume_text),
    }

    response = httpx.post(DEFAULT_API_URL, json=payload, timeout=120.0)
    response.raise_for_status()
    return response.json()


def stream_chat_request(
    user_prompt: str,
    resume_text: str,
) -> Iterator[dict[str, Any]]:
    payload: dict[str, Any] = {
        "message": build_backend_message(user_prompt, resume_text),
    }

    with httpx.stream(
        "POST",
        DEFAULT_STREAM_API_URL,
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
