"""Rendering helpers for chat responses."""
from __future__ import annotations

import json
from typing import Any

import streamlit as st


def render_backend_response(result: dict[str, Any]) -> None:
    request_type = result.get("request_type", "unknown")
    output = result.get("output", {})

    st.caption(f"Routed as `{request_type}`")

    if request_type == "analyze_job":
        _render_analysis(output)
    elif request_type == "tailor_resume":
        _render_tailored_resume(output)
    elif request_type == "draft_message":
        _render_outreach(output)
    elif request_type == "rejected":
        st.error(output.get("message", "Request was rejected by the backend."))
    else:
        st.json(output)

    with st.expander("Raw Backend Response"):
        st.code(json.dumps(result, indent=2), language="json")


def _render_analysis(output: dict[str, Any]) -> None:
    response = output.get("response")
    if response:
        st.markdown(response)

    memories = output.get("retrieved_memory", [])
    if memories:
        with st.expander("Retrieved Memory"):
            st.json(memories)


def _render_tailored_resume(output: dict[str, Any]) -> None:
    response = output.get("response")
    if response:
        st.markdown(response)


def _render_outreach(output: dict[str, Any]) -> None:
    outreach_message = output.get("outreach_message")
    email_version = output.get("email_version")

    if outreach_message:
        st.markdown("**Outreach Message**")
        st.write(outreach_message)
    if email_version:
        st.markdown("**Email Version**")
        st.write(email_version)
    if not outreach_message and not email_version:
        st.caption("No outreach content returned.")
