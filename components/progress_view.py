"""Simple dashboard for learner reasoning progress."""

from datetime import datetime
from typing import Any

import streamlit as st

from services.case_manager import get_case_for_student
from services.progress import get_progress_summary


def _display_time(value: str) -> str:
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%b %d, %Y %H:%M")
    except (TypeError, ValueError):
        return value or "Unknown date"


def render_progress(progress: dict[str, Any]) -> None:
    """Display aggregate reasoning metrics and recent learner attempts."""
    summary = get_progress_summary(progress)
    st.title("ECG Learning Progress")

    columns = st.columns(4)
    columns[0].metric("Cases completed", summary["cases_completed"])
    columns[1].metric("Reasoning attempts", summary["attempts"])
    columns[2].metric("Revisions", summary["revisions"])
    confidence = summary["average_confidence"]
    columns[3].metric("Average confidence", f"{confidence:.1f} / 5" if confidence is not None else "—")
    st.caption(f"Cases started: {summary['cases_started']}")

    st.subheader("Areas for Practice")
    if summary["areas_for_practice"]:
        for item in summary["areas_for_practice"]:
            st.markdown(f"- {item}")
    else:
        st.caption("More reasoning attempts are needed to identify recurring practice areas.")

    st.subheader("Strengths")
    if summary["top_strengths"]:
        for item in summary["top_strengths"]:
            st.markdown(f"- {item}")
    else:
        st.caption("Strengths will appear as consistent evidence builds across attempts.")

    st.subheader("Recent Improvements")
    if summary["recent_improvements"]:
        for improvement in summary["recent_improvements"]:
            st.markdown(f"- {improvement['message']}")
    else:
        st.caption("No resolved issues have been recorded yet.")

    if summary["confidence_reasoning_patterns"]:
        st.subheader("Confidence and Reasoning")
        for pattern in summary["confidence_reasoning_patterns"]:
            st.write(f"- {pattern}")

    st.subheader("Reasoning by ECG Step")
    labels = {
        "rate": "Rate",
        "rhythm": "Rhythm",
        "axis": "Axis",
        "p_waves": "P Waves",
        "pr_interval": "PR Interval",
        "qrs": "QRS",
        "st_t": "ST/T",
        "interpretation": "Interpretation",
        "overall_reasoning": "Overall Reasoning",
    }
    for step, label in labels.items():
        stats = summary["step_statistics"][step]
        st.write(
            f"**{label}** — attempts: {stats['attempts']} · issues: {stats['issues']} · "
            f"revisions: {stats['revisions']} · resolved: {stats['resolved_issues']}"
        )

    st.subheader("Recent Attempts")
    recent_attempts = summary["recent_attempts"]
    if not recent_attempts:
        st.caption("Submitted attempts will appear here.")
    for attempt in recent_attempts:
        safe_case = get_case_for_student(attempt.get("case_id", "")) or {}
        case_title = safe_case.get("title", attempt.get("case_id", "Unknown case"))
        feedback_used = attempt.get("hints_requested", 0) > 0
        confidence = attempt.get("confidence")
        with st.expander(f"{case_title} · {_display_time(attempt.get('timestamp', ''))}"):
            st.write(f"Confidence: {confidence if confidence is not None else 'Not recorded'} / 5")
            st.write(f"Feedback hints used: {'Yes' if feedback_used else 'No'}")
            st.write(f"Revised: {'Yes' if attempt.get('revised') else 'No'}")
            st.write(f"Attempt number: {attempt.get('attempt_number', '—')}")

    if summary["hints_requested"]:
        average_hint = summary["average_hint_level"]
        st.caption(
            f"Hints requested: {summary['hints_requested']} · "
            f"Average requested hint level: {average_hint:.1f}"
        )
