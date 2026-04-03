"""Session-state helpers for the Streamlit frontend."""
from __future__ import annotations

import streamlit as st

from frontend.models import ChatTurn, FrontendState, ResumeContext


STATE_KEY = "frontend_state"


def get_state() -> FrontendState:
    if STATE_KEY not in st.session_state:
        st.session_state[STATE_KEY] = FrontendState(
            chat_turns=[
                ChatTurn(
                    role="assistant",
                    text=(
                        "Upload a resume PDF, then paste the job description or ask for a job-fit analysis."
                    ),
                )
            ]
        )
    return st.session_state[STATE_KEY]


def set_resume(
    filename: str,
    text: str,
    *,
    file_token: str = "",
    page_count: int = 0,
    char_count: int = 0,
) -> None:
    state = get_state()
    state.resume = ResumeContext(
        filename=filename,
        text=text,
        file_token=file_token,
        page_count=page_count,
        char_count=char_count,
    )


def add_turn(role: str, text: str, backend_response: dict | None = None) -> None:
    state = get_state()
    state.chat_turns.append(
        ChatTurn(role=role, text=text, backend_response=backend_response)
    )


def clear_chat() -> None:
    st.session_state[STATE_KEY] = FrontendState(
        chat_turns=[
            ChatTurn(
                role="assistant",
                text=(
                    "Chat reset. Upload a resume PDF, then send a prompt to analyze a job description."
                ),
            )
        ]
    )
