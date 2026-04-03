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
    fit_summary = output.get("fit_summary")
    if fit_summary:
        st.markdown(fit_summary)

    matched = output.get("matched_skills", [])
    missing = output.get("missing_skills", [])
    recommendations = output.get("resume_recommendations", [])

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Matched Skills**")
        if matched:
            for item in matched:
                st.markdown(f"- `{item}`")
        else:
            st.caption("No matched skills returned.")

    with col2:
        st.markdown("**Missing Skills**")
        if missing:
            for item in missing:
                st.markdown(f"- `{item}`")
        else:
            st.caption("No missing skills returned.")

    st.markdown("**Resume Recommendations**")
    if recommendations:
        for item in recommendations:
            st.markdown(f"- {item}")
    else:
        st.caption("No recommendations returned.")

    memories = output.get("retrieved_memory", [])
    if memories:
        with st.expander("Retrieved Memory"):
            st.json(memories)


def _render_tailored_resume(output: dict[str, Any]) -> None:
    bullets = output.get("tailored_bullets", [])
    if bullets:
        st.markdown("**Tailored Bullets**")
        for bullet in bullets:
            st.markdown(f"- {bullet}")

    rationale = output.get("rationale")
    if rationale:
        st.markdown("**Rationale**")
        st.write(rationale)


def _render_outreach(output: dict[str, Any]) -> None:
    st.markdown("**Outreach Message**")
    st.write(output.get("outreach_message", ""))
    st.markdown("**Email Version**")
    st.write(output.get("email_version", ""))
