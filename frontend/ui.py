"""Chat-style Streamlit UI."""
from __future__ import annotations

import streamlit as st
from httpx import HTTPError

from frontend.models import ChatSessionState, ChatTurn, ResumeContext, SessionSummary
from frontend.rendering import render_backend_response
from frontend.services.api import (
    create_session,
    delete_session,
    get_session,
    list_sessions,
    save_session_resume,
    stream_chat_request,
)
from frontend.services.pdf import extract_resume
from frontend.state import (
    add_turn,
    get_state,
    set_active_session,
    set_initialized,
    set_sessions,
)


DEFAULT_ASSISTANT_MESSAGE = (
    "Upload a resume PDF, then paste the job description or ask for a job-fit analysis."
)


def run_app() -> None:
    st.set_page_config(
        page_title="ApplyGraph Chat",
        page_icon="AG",
        layout="wide",
    )
    _render_shell()
    _ensure_sessions_loaded()

    state = get_state()
    active_session = state.active_session
    active_resume = active_session.resume if active_session is not None else ResumeContext()
    active_turns = active_session.chat_turns if active_session is not None else []

    _render_sidebar()
    _render_workspace_intro(
        active_resume.filename,
        bool(active_resume.text),
        len(active_turns),
    )
    _render_chat(active_turns)

    prompt = st.chat_input(
        "Paste the job description or ask how your resume fits the role.",
        disabled=active_session is None or not bool(active_resume.filename),
    )
    if prompt and active_session is not None:
        _submit_prompt(prompt, active_session.id)


def _ensure_sessions_loaded() -> None:
    state = get_state()
    if state.initialized and state.active_session is not None:
        return
    try:
        summaries_payload = list_sessions()
        if not summaries_payload:
            active_payload = create_session()
            summaries_payload = list_sessions()
        else:
            active_session_id = state.active_session.id if state.active_session is not None else summaries_payload[0]["id"]
            active_payload = get_session(active_session_id)
    except HTTPError as exc:
        st.error(f"Could not load chat sessions: {exc}")
        return

    set_sessions([_summary_from_payload(item) for item in summaries_payload])
    set_active_session(_session_from_detail(active_payload))
    set_initialized()


def _render_shell() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 12% 18%, rgba(222, 121, 47, 0.20), transparent 24%),
                radial-gradient(circle at 88% 8%, rgba(91, 134, 110, 0.24), transparent 22%),
                linear-gradient(180deg, #16181b 0%, #1f2428 45%, #252b30 100%);
        }
        .block-container {
            max-width: 1100px;
            padding-top: 4.75rem;
            padding-bottom: 7rem;
        }
        [data-testid="stSidebar"] {
            background:
                linear-gradient(180deg, rgba(26, 30, 35, 0.98) 0%, rgba(19, 22, 26, 0.98) 100%);
            border-right: 1px solid rgba(255, 255, 255, 0.06);
        }
        [data-testid="stSidebarContent"] {
            padding-top: 0.6rem;
        }
        [data-testid="stSidebar"] * {
            color: #edf1e9;
        }
        [data-testid="stSidebar"] [data-testid="stFileUploader"] {
            margin-top: 0.15rem;
            margin-bottom: 1rem;
        }
        [data-testid="stSidebar"] [data-testid="stFileUploader"] section {
            border: 1px dashed rgba(255, 193, 122, 0.36);
            border-radius: 22px;
            background:
                linear-gradient(180deg, rgba(255, 161, 78, 0.12) 0%, rgba(255, 161, 78, 0.06) 100%);
            padding: 0.75rem 0.8rem;
        }
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
            background: rgba(8, 11, 15, 0.24);
        }
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] div {
            color: #f7f2e8;
            font-weight: 600;
        }
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] small {
            color: #d6c9b7;
        }
        [data-testid="stSidebar"] button {
            border-radius: 14px;
        }
        [data-testid="stSidebar"] [data-testid="stButton"] {
            margin-bottom: 0.06rem;
        }
        .new-chat-anchor [data-testid="stButton"] {
            margin-top: 0.02rem;
            margin-bottom: 0.08rem;
        }
        [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
            gap: 0.22rem;
            margin-bottom: 0 !important;
        }
        [data-testid="stSidebar"] button[kind="primary"] {
            background: linear-gradient(135deg, #3a332c 0%, #4c4034 100%);
            color: #fff7ed;
            border: 1px solid rgba(240, 174, 111, 0.24);
            font-weight: 700;
            min-height: 3.15rem;
            box-shadow: 0 10px 24px rgba(0, 0, 0, 0.16);
        }
        [data-testid="stSidebar"] button[kind="primary"]:hover {
            background: linear-gradient(135deg, #463b31 0%, #5a4939 100%);
            color: #fffaf3;
        }
        [data-testid="stSidebar"] [data-testid="column"] {
            display: flex;
            align-items: center;
        }
        [data-testid="stSidebar"] [data-testid="column"]:first-child {
            padding-right: 0.18rem;
        }
        [data-testid="stSidebar"] [data-testid="column"]:last-child {
            padding-left: 0;
        }
        [data-testid="stSidebar"] [data-testid="column"] [data-testid="stButton"] {
            margin-bottom: 0;
        }
        [data-testid="stSidebar"] [data-testid="column"] [data-testid="stButton"] button {
            min-height: 2.35rem;
        }
        [data-testid="stSidebar"] [data-testid="column"]:last-child [data-testid="stButton"] button {
            min-height: 2.35rem;
            padding: 0;
            font-size: 1.35rem;
            line-height: 1;
            box-shadow: none;
        }
        .sidebar-shell {
            display: grid;
            gap: 0.2rem;
        }
        .sidebar-main {
            display: grid;
            gap: 0.2rem;
        }
        .sidebar-kicker {
            font-size: 0.96rem;
            font-weight: 700;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: #f0ae6f;
        }
        .sidebar-copy {
            color: #d1d8cf;
            margin: 0;
            line-height: 1.45;
            font-size: 1.02rem;
        }
        .upload-callout {
            border-radius: 22px;
            padding: 1rem 1rem 1.05rem 1rem;
            background:
                linear-gradient(160deg, rgba(255, 173, 94, 0.18) 0%, rgba(255, 124, 57, 0.10) 100%);
            border: 1px solid rgba(255, 184, 119, 0.22);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
            margin: 0;
        }
        .upload-callout-label {
            color: #ffd5aa;
            font-size: 0.74rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            margin-bottom: 0.35rem;
        }
        .upload-callout-title {
            color: #fff7ed;
            font-size: 1.08rem;
            font-weight: 700;
            margin-bottom: 0.3rem;
        }
        .upload-callout-copy {
            color: #ecd9c4;
            font-size: 0.93rem;
            line-height: 1.45;
        }
        .resume-card {
            border-radius: 18px;
            padding: 0.95rem 1rem;
            background: rgba(239, 247, 240, 0.10);
            border: 1px solid rgba(167, 229, 186, 0.14);
            margin: 0;
        }
        .resume-card-label {
            color: #a5d5b0;
            font-size: 0.74rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            margin-bottom: 0.32rem;
        }
        .resume-card-value {
            color: #f4f7ef;
            font-size: 0.98rem;
            font-weight: 600;
            line-height: 1.4;
        }
        .resume-card-copy {
            color: #b7c4b7;
            margin-top: 0.35rem;
            font-size: 0.9rem;
            line-height: 1.4;
        }
        [data-testid="stChatMessage"] {
            background: rgba(248, 243, 233, 0.94);
            border: 1px solid rgba(33, 39, 33, 0.07);
            border-radius: 24px;
            padding: 0.9rem 1rem;
            box-shadow: 0 18px 45px rgba(0, 0, 0, 0.08);
            margin-bottom: 0.85rem;
        }
        [data-testid="stChatMessageContent"] p,
        [data-testid="stChatMessageContent"] li,
        [data-testid="stChatMessageContent"] span {
            color: #1e2821;
        }
        [data-testid="stChatInput"] {
            background: rgba(19, 23, 27, 0.94);
            border-top: 1px solid rgba(255, 255, 255, 0.07);
            backdrop-filter: blur(10px);
        }
        .hero {
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 22px;
            background:
                linear-gradient(135deg, rgba(242, 235, 223, 0.96) 0%, rgba(231, 220, 199, 0.95) 100%);
            padding: 1.05rem 1.15rem;
            box-shadow: 0 20px 60px rgba(9, 12, 16, 0.12);
            margin-bottom: 0.8rem;
            width: min(100%, 760px);
        }
        .hero-inner {
            max-width: 38rem;
        }
        .hero h1 {
            margin: 0;
            color: #182119;
            font-size: 1.85rem;
            line-height: 1.06;
        }
        .hero p {
            margin: 0.45rem 0 0 0;
            color: #485349;
            max-width: 30rem;
            font-size: 0.92rem;
            line-height: 1.45;
        }
        .workspace-note {
            border-radius: 18px;
            padding: 0.95rem 1.05rem;
            background:
                linear-gradient(135deg, rgba(29, 35, 39, 0.88) 0%, rgba(38, 44, 49, 0.90) 100%);
            border: 1px solid rgba(255, 255, 255, 0.06);
            color: #eef1eb;
            margin-bottom: 0.9rem;
            box-shadow: 0 18px 52px rgba(8, 11, 13, 0.14);
        }
        .workspace-note-label {
            color: #9fb3a2;
            font-size: 0.69rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            margin-bottom: 0.28rem;
        }
        .workspace-note-title {
            color: #f4f6ef;
            font-size: 0.98rem;
            font-weight: 700;
            margin-bottom: 0.18rem;
        }
        .workspace-note-copy {
            color: #c9d1c8;
            margin: 0;
            font-size: 0.9rem;
            line-height: 1.4;
        }
        </style>
        <div class="hero">
            <div class="hero-inner">
                <h1>Chat with your resume in context.</h1>
                <p>Each conversation keeps its own resume, memory, and message history.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_sidebar() -> None:
    state = get_state()
    active_session = state.active_session

    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-shell">
                <div class="sidebar-main">
                    <div>
                        <div class="sidebar-kicker">ApplyGraph</div>
                        <div class="sidebar-copy">Create multiple chat threads and keep resume context and semantic memory isolated per session.</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="new-chat-anchor">', unsafe_allow_html=True)
        if st.button("New chat", key="new-chat-primary", use_container_width=True, type="primary"):
            reusable_session_id = _find_reusable_empty_session_id()
            if reusable_session_id is not None:
                detail = get_session(reusable_session_id)
            else:
                detail = create_session()
            summaries = list_sessions()
            set_sessions([_summary_from_payload(item) for item in summaries])
            current_token = active_session.resume.file_token if active_session is not None else ""
            set_active_session(_session_from_detail(detail, file_token=current_token if detail["id"] == (active_session.id if active_session else "") else ""))
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        for summary in state.sessions:
            label = summary.title if len(summary.title) <= 28 else f"{summary.title[:25]}..."
            is_active = active_session is not None and summary.id == active_session.id
            session_cols = st.columns([5, 1], gap="small", vertical_alignment="center")
            with session_cols[0]:
                if st.button(
                    label,
                    key=f"session-{summary.id}",
                    use_container_width=True,
                    type="secondary",
                ):
                    detail = get_session(summary.id)
                    current_token = active_session.resume.file_token if is_active and active_session else ""
                    set_active_session(_session_from_detail(detail, file_token=current_token))
                    st.rerun()
            with session_cols[1]:
                if st.button("×", key=f"delete-session-{summary.id}", use_container_width=True):
                    _delete_session(summary.id)
                    st.rerun()

        st.markdown(
            """
            <div class="upload-callout">
                <div class="upload-callout-label">Resume</div>
                <div class="upload-callout-title">Upload the resume PDF</div>
                <div class="upload-callout-copy">The uploaded resume is stored on the currently selected chat session.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        uploaded_file = st.file_uploader("Resume PDF", type=["pdf"], label_visibility="collapsed")
        if uploaded_file is not None:
            if active_session is None:
                st.error("Create a chat session first.")
            else:
                file_bytes = uploaded_file.getvalue()
                file_token = f"{uploaded_file.name}:{len(file_bytes)}"
                if file_token != active_session.resume.file_token:
                    extraction_status = st.status("Reading resume PDF...", expanded=True)
                    try:
                        extraction = extract_resume(file_bytes)
                    except Exception as exc:
                        extraction_status.update(label="Resume import failed", state="error", expanded=True)
                        st.error(f"Could not read the uploaded PDF: {exc}")
                    else:
                        extraction_status.write(f"Processed {extraction.page_count} page(s)")
                        extraction_status.write(f"Extracted {extraction.char_count} characters of profile text")
                        if extraction.text:
                            try:
                                detail = save_session_resume(
                                    active_session.id,
                                    filename=uploaded_file.name,
                                    text=extraction.text,
                                    page_count=extraction.page_count,
                                    char_count=extraction.char_count,
                                )
                            except HTTPError as exc:
                                extraction_status.update(label="Resume save failed", state="error", expanded=True)
                                st.error(f"Could not save the resume to the backend session: {exc}")
                            else:
                                set_active_session(_session_from_detail(detail, file_token=file_token))
                                summaries = list_sessions()
                                set_sessions([_summary_from_payload(item) for item in summaries])
                                extraction_status.update(label="Resume ready", state="complete", expanded=False)
                                st.rerun()
                        else:
                            extraction_status.update(label="No readable text found", state="error", expanded=True)
                            st.warning("The PDF was uploaded, but no readable text was extracted.")

        current_filename = active_session.resume.filename if active_session is not None else ""
        if current_filename:
            st.markdown(
                f"""
                <div class="resume-card">
                    <div class="resume-card-label">Active Resume</div>
                    <div class="resume-card-value">{current_filename}</div>
                    <div class="resume-card-copy">This chat will reuse the uploaded resume for retrieval and generation.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if active_session and (active_session.resume.page_count or active_session.resume.char_count):
                st.caption(
                    f"{active_session.resume.page_count} page(s) • {active_session.resume.char_count} characters extracted"
                )
        else:
            st.markdown(
                """
                <div class="resume-card">
                    <div class="resume-card-label">Active Resume</div>
                    <div class="resume-card-value">No resume loaded yet</div>
                    <div class="resume-card-copy">Upload a PDF above to unlock the chat input for this session.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_workspace_intro(current_filename: str, has_resume: bool, chat_turn_count: int) -> None:
    if chat_turn_count > 1:
        return

    if has_resume:
        heading = "Resume loaded"
        copy = f"{current_filename}. Paste the job description in chat to start the analysis for this session."
    else:
        heading = "Upload a resume to begin"
        copy = "Each chat keeps its own uploaded resume and memory context."

    st.markdown(
        f"""
        <div class="workspace-note">
            <div class="workspace-note-label">Workspace</div>
            <div class="workspace-note-title">{heading}</div>
            <p class="workspace-note-copy">{copy}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_chat(chat_turns: list[ChatTurn]) -> None:
    for turn in chat_turns:
        with st.chat_message(turn.role):
            if turn.role == "assistant" and turn.backend_response is not None:
                render_backend_response(turn.backend_response)
            else:
                st.write(turn.text)


def _submit_prompt(prompt: str, session_id: str) -> None:
    add_turn("user", prompt)
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        status_box = st.status("Working through the request...", expanded=True)
        result: dict | None = None
        try:
            for event in stream_chat_request(session_id=session_id, user_prompt=prompt):
                event_type = event.get("type")
                if event_type == "stage":
                    _render_stage_update(status_box, event)
                elif event_type == "final":
                    result = event.get("data")
                elif event_type == "error":
                    raise RuntimeError(event.get("message", "Streaming request failed"))
        except (HTTPError, RuntimeError) as exc:
            status_box.update(label="Backend request failed", state="error", expanded=True)
            st.error(str(exc))
            add_turn("assistant", f"Backend request failed: {exc}")
            return

        if result is None:
            status_box.update(label="Backend request failed", state="error", expanded=True)
            st.error("The backend stream ended without a final response.")
            add_turn("assistant", "Backend request failed: stream ended without a final response.")
            return

        status_box.update(label="Analysis ready", state="complete", expanded=False)
        render_backend_response(result)
        add_turn("assistant", text="", backend_response=result)
        _refresh_active_session_from_backend()


def _refresh_active_session_from_backend() -> None:
    state = get_state()
    if state.active_session is None:
        return
    current_token = state.active_session.resume.file_token
    detail = get_session(state.active_session.id)
    set_active_session(_session_from_detail(detail, file_token=current_token))
    set_sessions([_summary_from_payload(item) for item in list_sessions()])


def _render_stage_update(status_box, event: dict) -> None:
    stage = str(event.get("stage", "")).replace("_", " ").title()
    status = event.get("status", "completed")
    message = event.get("message") or stage
    meta = event.get("meta", {})

    if status == "started":
        status_box.update(label=message, state="running", expanded=True)
        status_box.write(f"Starting {stage.lower()}...")
        return

    detail = _format_stage_detail(event.get("stage", ""), meta)
    if detail:
        status_box.write(f"{message} - {detail}")
    else:
        status_box.write(f"{message} complete")


def _format_stage_detail(stage: str, meta: dict) -> str:
    if not meta:
        return ""
    if stage == "prepare_request":
        request_type = meta.get("request_type")
        if request_type == "rejected" and meta.get("guardrail_reason"):
            return meta["guardrail_reason"]
        if request_type:
            return f"routed to {request_type}"
    if stage == "parse_input":
        return (
            f"{meta.get('job_skill_count', 0)} job skill(s), "
            f"{meta.get('profile_skill_count', 0)} profile skill(s)"
        )
    if stage == "classify_request" and meta.get("request_type"):
        return f"confirmed {meta['request_type']}"
    if stage == "retrieve_memory":
        return f"{meta.get('memory_count', 0)} memory item(s)"
    if stage == "generate_output":
        keys = meta.get("keys", [])
        if keys:
            return ", ".join(keys)
    if stage == "persist_memory":
        return f"{meta.get('saved_memory_count', 0)} item(s) saved"
    if stage == "review_output" and meta.get("errors"):
        return ", ".join(meta["errors"])
    return ""


def _summary_from_payload(payload: dict) -> SessionSummary:
    return SessionSummary(
        id=payload["id"],
        title=payload["title"],
        updated_at=payload.get("updated_at", ""),
        created_at=payload.get("created_at", ""),
        resume_filename=payload.get("resume_filename") or "",
        message_count=payload.get("message_count", 0),
    )


def _find_reusable_empty_session_id() -> str | None:
    state = get_state()
    for session in state.sessions:
        if session.message_count == 0 and not session.resume_filename:
            return session.id
    return None


def _delete_session(session_id: str) -> None:
    state = get_state()
    delete_session(session_id)
    summaries = list_sessions()
    if not summaries:
        detail = create_session()
        summaries = list_sessions()
    else:
        remaining_ids = {item["id"] for item in summaries}
        current_active_id = state.active_session.id if state.active_session is not None else None
        next_session_id = None
        if current_active_id and current_active_id in remaining_ids and current_active_id != session_id:
            next_session_id = current_active_id
        else:
            next_session_id = summaries[0]["id"]
        detail = get_session(next_session_id)
    set_sessions([_summary_from_payload(item) for item in summaries])
    set_active_session(_session_from_detail(detail))


def _session_from_detail(payload: dict, *, file_token: str = "") -> ChatSessionState:
    messages = [
        ChatTurn(
            role=message["role"],
            text=message.get("content", ""),
            backend_response=message.get("backend_response"),
        )
        for message in payload.get("messages", [])
    ]
    if not messages:
        messages = [ChatTurn(role="assistant", text=DEFAULT_ASSISTANT_MESSAGE)]

    return ChatSessionState(
        id=payload["id"],
        title=payload["title"],
        created_at=payload.get("created_at", ""),
        updated_at=payload.get("updated_at", ""),
        chat_turns=messages,
        resume=ResumeContext(
            filename=payload.get("resume_filename") or "",
            text="loaded" if payload.get("resume_filename") else "",
            file_token=file_token,
            page_count=payload.get("resume_page_count", 0),
            char_count=payload.get("resume_char_count", 0),
        ),
    )
