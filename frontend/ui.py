"""Chat-style Streamlit UI."""
from __future__ import annotations

import streamlit as st
from httpx import HTTPError

from frontend.rendering import render_backend_response
from frontend.services.api import stream_chat_request
from frontend.services.pdf import extract_resume
from frontend.state import add_turn, clear_chat, get_state, set_resume


def run_app() -> None:
    st.set_page_config(
        page_title="ApplyGraph Chat",
        page_icon="AG",
        layout="wide",
    )
    _render_shell()

    state = get_state()
    _render_sidebar(state.resume.filename)
    _render_workspace_intro(state.resume.filename, bool(state.resume.text), len(state.chat_turns))
    _render_chat(state.chat_turns)

    prompt = st.chat_input(
        "Paste the job description or ask how your resume fits the role.",
        disabled=not bool(state.resume.text),
    )
    if prompt:
        _submit_prompt(prompt, state.resume.text)


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
        [data-testid="stSidebarUserContent"] {
            min-height: calc(100vh - 3rem);
            display: flex;
            flex-direction: column;
        }
        [data-testid="stSidebarUserContent"] > div {
            min-height: 100%;
            display: flex;
            flex-direction: column;
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
        [data-testid="stSidebar"] button[kind="secondary"] {
            border-radius: 14px;
        }
        .sidebar-shell {
            display: grid;
            gap: 1rem;
        }
        .sidebar-main {
            display: grid;
            gap: 1rem;
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
        .sidebar-footer {
            margin-top: auto;
            padding-top: 1.2rem;
            display: flex;
            flex-direction: column;
        }
        .sidebar-footer [data-testid="stButton"] {
            margin-top: auto;
        }
        .sidebar-footer button {
            width: 100%;
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
            display: flex;
            flex-direction: column;
            justify-content: center;
            min-height: 0;
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
                <p>Upload the resume, then paste the JD in chat.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_sidebar(current_filename: str) -> None:
    state = get_state()
    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-shell">
                <div class="sidebar-main">
                    <div>
                        <div class="sidebar-kicker">ApplyGraph</div>
                        <div class="sidebar-copy">Load the candidate resume first, then use the chat to evaluate any job description against it.</div>
                    </div>
                    <div class="upload-callout">
                        <div class="upload-callout-label">Step 1</div>
                        <div class="upload-callout-title">Upload the resume PDF</div>
                        <div class="upload-callout-copy">This is the profile context attached to every backend request in the chat.</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        uploaded_file = st.file_uploader("Resume PDF", type=["pdf"], label_visibility="collapsed")
        if uploaded_file is not None:
            file_bytes = uploaded_file.getvalue()
            file_token = f"{uploaded_file.name}:{len(file_bytes)}"
            if file_token != state.resume.file_token:
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
                        set_resume(
                            uploaded_file.name,
                            extraction.text,
                            file_token=file_token,
                            page_count=extraction.page_count,
                            char_count=extraction.char_count,
                        )
                        extraction_status.update(label="Resume ready", state="complete", expanded=False)
                    else:
                        extraction_status.update(label="No readable text found", state="error", expanded=True)
                        st.warning("The PDF was uploaded, but no readable text was extracted.")

        current_filename = state.resume.filename or current_filename

        if current_filename:
            st.markdown(
                f"""
                <div class="resume-card">
                    <div class="resume-card-label">Active Resume</div>
                    <div class="resume-card-value">{current_filename}</div>
                    <div class="resume-card-copy">The chat will use this uploaded PDF as the candidate profile context.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if state.resume.page_count or state.resume.char_count:
                st.caption(
                    f"{state.resume.page_count} page(s) • {state.resume.char_count} characters extracted"
                )
        else:
            st.markdown(
                """
                <div class="resume-card">
                    <div class="resume-card-label">Active Resume</div>
                    <div class="resume-card-value">No resume loaded yet</div>
                    <div class="resume-card-copy">Upload a PDF above to unlock the chat input and start analysis.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        footer = st.container()
        with footer:
            st.markdown('<div class="sidebar-footer">', unsafe_allow_html=True)
            if st.button("Reset Chat", use_container_width=True):
                clear_chat()
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)


def _render_workspace_intro(
    current_filename: str,
    has_resume: bool,
    chat_turn_count: int,
) -> None:
    if chat_turn_count > 1:
        return

    if has_resume:
        heading = "Resume loaded"
        copy = f"{current_filename}. Paste the job description in chat to start the analysis."
    else:
        heading = "Upload a resume to begin"
        copy = "The chat unlocks after the PDF is loaded from the sidebar."

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


def _render_chat(chat_turns: list) -> None:
    for turn in chat_turns:
        with st.chat_message(turn.role):
            if turn.role == "assistant" and turn.backend_response is not None:
                render_backend_response(turn.backend_response)
            else:
                st.write(turn.text)


def _submit_prompt(prompt: str, resume_text: str) -> None:
    add_turn("user", prompt)
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        status_box = st.status("Working through the request...", expanded=True)
        result: dict | None = None
        try:
            for event in stream_chat_request(
                user_prompt=prompt,
                resume_text=resume_text,
            ):
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
        add_turn(
            "assistant",
            text="",
            backend_response=result,
        )


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
