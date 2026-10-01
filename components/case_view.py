"""Learner-facing presentation for an ECG educational case."""

from typing import Any

import streamlit as st

from components.reasoning_form import render_feedback_and_revision, render_reasoning_form
from services.image_preprocessor import resolve_learner_image_path


def render_case(case: dict[str, Any], reference_case: dict[str, Any]) -> None:
    """Display a student-safe case without revealing reference answers."""
    st.header(case["title"])
    st.caption(f"Difficulty: {case['difficulty']}")
    st.write(case["description"])

    st.subheader("Learning objectives")
    for objective in case["learning_objectives"]:
        st.markdown(f"- {objective}")

    image_path = case.get("image_path")
    learner_image = resolve_learner_image_path(image_path) if image_path else None
    if learner_image and learner_image.is_file():
        st.image(str(learner_image), caption="ECG case")
        attribution = " · ".join(
            value for value in (case.get("source_name"), case.get("license"), case.get("source_record")) if value
        )
        if attribution:
            st.caption(f"Image source: {attribution}")
        if case.get("source_url"):
            st.markdown(f"[View source record]({case['source_url']})")
    else:
        st.info("No sourced ECG image is available yet. This case can still be completed using the reasoning workflow.")

    st.divider()
    if st.session_state.get("reasoning_submitted"):
        st.success("Your reasoning has been recorded and evaluated internally.")
        render_feedback_and_revision()
    else:
        render_reasoning_form(case["id"], reference_case)
