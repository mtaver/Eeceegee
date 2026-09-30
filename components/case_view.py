"""Learner-facing presentation for an ECG educational case."""

from pathlib import Path
from typing import Any

import streamlit as st


def render_case(case: dict[str, Any]) -> None:
    """Display a student-safe case without revealing reference answers."""
    st.header(case["title"])
    st.caption(f"Difficulty: {case['difficulty']}")
    st.write(case["description"])

    st.subheader("Learning objectives")
    for objective in case["learning_objectives"]:
        st.markdown(f"- {objective}")

    image_path = case.get("ecg_image")
    if image_path:
        resolved_image = Path(__file__).resolve().parent.parent / image_path
        if resolved_image.is_file():
            st.image(str(resolved_image), caption="ECG case")
        else:
            st.info("ECG image will be added for this case.")
    else:
        st.info("ECG image will be added for this case.")
