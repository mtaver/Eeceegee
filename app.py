"""Streamlit entry point for ECG Learning Coach."""

import streamlit as st

from components.case_view import render_case
from services.case_manager import (
    get_case_for_student,
    get_cases_by_difficulty,
    get_available_difficulties,
)


st.set_page_config(page_title="ECG Learning Coach", page_icon="🫀", layout="centered")

st.title("ECG Learning Coach")
st.write(
    "Learn to interpret ECGs by improving your clinical reasoning—not by simply receiving the diagnosis."
)

if "selected_case_id" not in st.session_state:
    st.session_state.selected_case_id = None
if "case_started" not in st.session_state:
    st.session_state.case_started = False

if st.session_state.case_started and st.session_state.selected_case_id:
    case = get_case_for_student(st.session_state.selected_case_id)
    if case is None:
        st.warning("That case is no longer available. Please choose another case.")
        st.session_state.selected_case_id = None
        st.session_state.case_started = False
        st.rerun()

    render_case(case)
    st.divider()
    st.caption("The guided learning workflow will be added in a future step.")
    if st.button("Back to Cases"):
        st.session_state.selected_case_id = None
        st.session_state.case_started = False
        st.rerun()
else:
    st.subheader("Choose your learning level")
    difficulties = get_available_difficulties()
    if not difficulties:
        st.error("No learning cases are currently available.")
    else:
        difficulty = st.selectbox("Difficulty", difficulties)
        cases = get_cases_by_difficulty(difficulty)
        if not cases:
            st.info("No cases are available at this difficulty yet.")
        else:
            case_labels = {case["id"]: case["title"] for case in cases}
            selected_case_id = st.selectbox(
                "Choose a case",
                options=list(case_labels),
                format_func=lambda case_id: case_labels[case_id],
                key="case_selection",
            )
            if st.button("Start Case", type="primary"):
                st.session_state.selected_case_id = selected_case_id
                st.session_state.case_started = True
                st.rerun()
