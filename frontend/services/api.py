"""Backend request helpers for the Streamlit frontend."""
from __future__ import annotations

from typing import Any

import httpx


DEFAULT_API_URL = "http://localhost:8000/chat"


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
