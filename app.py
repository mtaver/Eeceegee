"""Streamlit entry point for ECG Learning Coach."""

import streamlit as st

from components.case_view import render_case
from components.progress_view import render_progress
from services.case_manager import (
    get_case_for_student,
    get_cases_by_difficulty,
    get_available_difficulties,
)
from services.progress import initialize_progress_session, record_case_started
from services.case_manager import get_case_by_id


st.set_page_config(page_title="ECG Learning Coach", page_icon="🫀", layout="centered")

st.title("ECG Learning Coach")
st.write(
    "Learn to interpret ECGs by improving your clinical reasoning—not by simply receiving the diagnosis."
)
initialize_progress_session(st.session_state)
st.session_state.setdefault("page", "Learning Cases")

page = st.radio(
    "Go to",
    ("Learning Cases", "Progress"),
    horizontal=True,
    key="page",
    label_visibility="collapsed",
)

if "selected_case_id" not in st.session_state:
    st.session_state.selected_case_id = None
if "case_started" not in st.session_state:
    st.session_state.case_started = False

if page == "Progress":
    render_progress(st.session_state.progress)
elif st.session_state.case_started and st.session_state.selected_case_id:
    case = get_case_for_student(st.session_state.selected_case_id)
    reference_case = get_case_by_id(st.session_state.selected_case_id)
    if case is None or reference_case is None:
        st.warning("That case is no longer available. Please choose another case.")
        st.session_state.selected_case_id = None
        st.session_state.case_started = False
        st.rerun()

    render_case(case, reference_case)
    if st.button("Back to Cases"):
        st.session_state.selected_case_id = None
        st.session_state.case_started = False
        st.session_state.reasoning_draft = None
        st.session_state.reasoning_submitted = False
        st.session_state.reasoning_evaluation = None
        st.session_state.reasoning_feedback = []
        st.session_state.reasoning_step = 0
        for widget_key in (
            "reasoning_rate_answer",
            "reasoning_rate_reasoning",
            "reasoning_rhythm_answer",
            "reasoning_rhythm_reasoning",
            "reasoning_axis_answer",
            "reasoning_axis_reasoning",
            "reasoning_p_waves_answer",
            "reasoning_p_waves_reasoning",
            "reasoning_pr_interval_answer",
            "reasoning_pr_interval_reasoning",
            "reasoning_qrs_answer",
            "reasoning_qrs_reasoning",
            "reasoning_st_t_answer",
            "reasoning_st_t_reasoning",
            "reasoning_interpretation",
            "reasoning_overall_reasoning",
            "reasoning_confidence",
        ):
            st.session_state.pop(widget_key, None)
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
                if st.session_state.get("selected_case_id") != selected_case_id:
                    st.session_state.reasoning_draft = None
                    st.session_state.reasoning_step = 0
                    st.session_state.reasoning_submitted = False
                    st.session_state.reasoning_evaluation = None
                    st.session_state.reasoning_feedback = []
                st.session_state.selected_case_id = selected_case_id
                st.session_state.case_started = True
                record_case_started(st.session_state.progress, selected_case_id)
                st.rerun()
