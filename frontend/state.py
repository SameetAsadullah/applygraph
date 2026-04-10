"""Session-state helpers for the Streamlit frontend."""
from __future__ import annotations

import streamlit as st

from frontend.models import ChatSessionState, ChatTurn, FrontendState, ResumeContext, SessionSummary


STATE_KEY = "frontend_state"


def get_state() -> FrontendState:
    if STATE_KEY not in st.session_state:
        st.session_state[STATE_KEY] = FrontendState()
    return st.session_state[STATE_KEY]


def set_sessions(session_summaries: list[SessionSummary]) -> None:
    state = get_state()
    state.sessions = session_summaries


def set_active_session(session: ChatSessionState) -> None:
    state = get_state()
    state.active_session = session
    state.initialized = True


def set_active_resume(
    filename: str,
    text: str,
    *,
    file_token: str = "",
    page_count: int = 0,
    char_count: int = 0,
) -> None:
    state = get_state()
    if state.active_session is None:
        return
    state.active_session.resume = ResumeContext(
        filename=filename,
        text=text,
        file_token=file_token,
        page_count=page_count,
        char_count=char_count,
    )
    for session in state.sessions:
        if session.id == state.active_session.id:
            session.resume_filename = filename


def add_turn(role: str, text: str, backend_response: dict | None = None) -> None:
    state = get_state()
    if state.active_session is None:
        return
    state.active_session.chat_turns.append(
        ChatTurn(role=role, text=text, backend_response=backend_response)
    )


def update_active_session_title(title: str) -> None:
    state = get_state()
    if state.active_session is None:
        return
    state.active_session.title = title
    for session in state.sessions:
        if session.id == state.active_session.id:
            session.title = title


def set_initialized() -> None:
    state = get_state()
    state.initialized = True
