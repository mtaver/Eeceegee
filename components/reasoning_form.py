"""Step-by-step learner ECG reasoning form."""

from copy import deepcopy
from typing import Any

import streamlit as st

from services.reasoning import (
    FINDING_FIELDS,
    create_reasoning_attempt,
    set_confidence,
    validate_reasoning_attempt,
)
from services.evaluator import evaluate_attempt
from services.feedback import generate_feedback, get_hint, MAX_HINT_LEVEL


STEPS = (
    ("Rate", "rate"),
    ("Rhythm", "rhythm"),
    ("Axis", "axis"),
    ("P waves", "p_waves"),
    ("PR interval", "pr_interval"),
    ("QRS", "qrs"),
    ("ST/T", "st_t"),
    ("Overall interpretation", "interpretation"),
    ("Overall reasoning", "overall_reasoning"),
    ("Confidence", "confidence"),
)


def _get_draft(case_id: str) -> dict[str, Any]:
    """Get or initialize the current case's session-persisted draft."""
    draft = st.session_state.get("reasoning_draft")
    if not isinstance(draft, dict) or draft.get("case_id") != case_id:
        draft = create_reasoning_attempt(case_id)
        st.session_state.reasoning_draft = draft
        st.session_state.reasoning_step = 0
        for widget_key in _widget_keys():
            st.session_state.pop(widget_key, None)
    return draft


def _widget_keys() -> tuple[str, ...]:
    """Keys used by this form, for clearing answers when starting another case."""
    finding_keys = tuple(
        key
        for field in FINDING_FIELDS
        for key in (f"reasoning_{field}_answer", f"reasoning_{field}_reasoning")
    )
    return finding_keys + (
        "reasoning_interpretation",
        "reasoning_overall_reasoning",
        "reasoning_confidence",
    )


def _seed_widget_values(draft: dict[str, Any], field: str) -> None:
    """Restore this step's widget values from the session-persisted draft."""
    if field in FINDING_FIELDS:
        section = draft[field]
        if field == "rate" and section["answer"]:
            try:
                rate_value = int(section["answer"])
            except (TypeError, ValueError):
                rate_value = None
            if rate_value is not None:
                st.session_state.setdefault("reasoning_rate_answer", rate_value)
        else:
            st.session_state.setdefault(f"reasoning_{field}_answer", section["answer"])
        st.session_state.setdefault(f"reasoning_{field}_reasoning", section["reasoning"])
    elif field in ("interpretation", "overall_reasoning"):
        st.session_state.setdefault(f"reasoning_{field}", draft[field])
    elif field == "confidence" and draft["confidence"] is not None:
        st.session_state.setdefault("reasoning_confidence", draft["confidence"])


def _store_widget_values(draft: dict[str, Any], field: str) -> None:
    if field in FINDING_FIELDS:
        draft[field]["answer"] = st.session_state.get(f"reasoning_{field}_answer", "")
        draft[field]["reasoning"] = st.session_state.get(f"reasoning_{field}_reasoning", "")
    elif field in ("interpretation", "overall_reasoning"):
        draft[field] = st.session_state.get(f"reasoning_{field}", "")
    elif field == "confidence":
        set_confidence(draft, int(st.session_state.get("reasoning_confidence", 1)))


def _render_finding_step(draft: dict[str, Any], field: str) -> None:
    section = draft[field]
    if field == "rate":
        st.number_input(
            "What is the ventricular rate?",
            min_value=1,
            max_value=300,
            step=1,
            value=None,
            placeholder="Enter beats per minute",
            key="reasoning_rate_answer",
        )
        # Keep a text representation in the model so all observations share one shape.
        if st.session_state.get("reasoning_rate_answer") is not None:
            section["answer"] = str(st.session_state["reasoning_rate_answer"])
        else:
            section["answer"] = ""
        st.text_area("How did you determine the rate?", key="reasoning_rate_reasoning")
        section["reasoning"] = st.session_state.get("reasoning_rate_reasoning", "")
    elif field == "rhythm":
        st.selectbox(
            "Is the rhythm regular, regularly irregular, or irregularly irregular?",
            ("", "Regular", "Regularly irregular", "Irregularly irregular", "Unable to determine"),
            key="reasoning_rhythm_answer",
        )
        st.text_area("What features of the ECG support your answer?", key="reasoning_rhythm_reasoning")
        _store_widget_values(draft, field)
    elif field == "axis":
        st.selectbox(
            "What is the likely cardiac axis?",
            ("", "Normal", "Left axis deviation", "Right axis deviation", "Extreme axis", "Unable to determine"),
            key="reasoning_axis_answer",
        )
        st.text_area("What findings led you to this conclusion?", key="reasoning_axis_reasoning")
        _store_widget_values(draft, field)
    elif field == "p_waves":
        st.text_area("Describe the P waves.", key="reasoning_p_waves_answer")
        st.text_area(
            "What is the relationship between the P waves and QRS complexes?",
            key="reasoning_p_waves_reasoning",
        )
        _store_widget_values(draft, field)
    elif field == "pr_interval":
        st.selectbox(
            "How would you describe the PR interval?",
            ("", "Normal", "Prolonged", "Short", "Unable to determine"),
            key="reasoning_pr_interval_answer",
        )
        st.text_area("Why?", key="reasoning_pr_interval_reasoning")
        _store_widget_values(draft, field)
    elif field == "qrs":
        st.selectbox(
            "How would you describe the QRS complex?",
            ("", "Narrow", "Wide", "Unable to determine"),
            key="reasoning_qrs_answer",
        )
        st.text_area("What does this finding suggest?", key="reasoning_qrs_reasoning")
        _store_widget_values(draft, field)
    elif field == "st_t":
        st.selectbox(
            "Are there significant ST-segment or T-wave abnormalities?",
            ("", "No obvious abnormality", "ST elevation", "ST depression", "T-wave abnormality", "Unable to determine"),
            key="reasoning_st_t_answer",
        )
        st.text_area("Describe what you observe.", key="reasoning_st_t_reasoning")
        _store_widget_values(draft, field)
    else:
        raise ValueError(f"Unknown finding field: {field}")


def render_reasoning_form(case_id: str, reference_case: dict[str, Any]) -> None:
    """Render one workflow step at a time and store a completed attempt."""
    draft = _get_draft(case_id)
    step_index = int(st.session_state.get("reasoning_step", 0))
    step_index = min(max(step_index, 0), len(STEPS) - 1)
    step_name, field = STEPS[step_index]
    _seed_widget_values(draft, field)

    st.subheader(f"Step {step_index + 1} of {len(STEPS)} — {step_name}")
    st.progress((step_index + 1) / len(STEPS))

    if field in FINDING_FIELDS:
        _render_finding_step(draft, field)
    elif field == "interpretation":
        st.text_area(
            "Based on your findings, what is your overall ECG interpretation?",
            height=140,
            key="reasoning_interpretation",
        )
        draft[field] = st.session_state.get("reasoning_interpretation", "")
    elif field == "overall_reasoning":
        st.text_area(
            "Explain how your findings led you to your interpretation.",
            height=220,
            key="reasoning_overall_reasoning",
        )
        draft[field] = st.session_state.get("reasoning_overall_reasoning", "")
    else:
        confidence = st.select_slider(
            "How confident are you in your interpretation?",
            options=[1, 2, 3, 4, 5],
            value=st.session_state.get("reasoning_confidence", 3),
            format_func=lambda value: {
                1: "1 — Not confident",
                5: "5 — Very confident",
            }.get(value, str(value)),
            key="reasoning_confidence",
        )
        set_confidence(draft, confidence)

    if step_index < len(STEPS) - 1:
        col_back, col_next = st.columns(2)
        with col_back:
            if step_index > 0 and st.button("Back", key=f"back_{step_index}"):
                st.session_state.reasoning_step = step_index - 1
                st.rerun()
        with col_next:
            if st.button("Next", key=f"next_{step_index}"):
                # Validate only the current section so future steps need not be filled yet.
                current_errors = _validate_current_step(draft, field)
                if current_errors:
                    st.warning(current_errors[0])
                else:
                    st.session_state.reasoning_step = step_index + 1
                    st.rerun()
    else:
        col_back, col_submit = st.columns(2)
        with col_back:
            if st.button("Back", key=f"back_{step_index}"):
                st.session_state.reasoning_step = step_index - 1
                st.rerun()
        with col_submit:
            if st.button("Submit Reasoning", type="primary"):
                errors = validate_reasoning_attempt(draft)
                if errors:
                    st.warning(errors[0])
                else:
                    st.session_state.completed_reasoning_attempt = deepcopy(draft)
                    evaluation = evaluate_attempt(
                        reference_case,
                        draft,
                    )
                    st.session_state.reasoning_evaluation = evaluation.to_dict()
                    st.session_state.reasoning_feedback = [
                        item.to_dict() for item in generate_feedback(evaluation)
                    ]
                    st.session_state.reasoning_submitted = True
                    st.rerun()

    if st.session_state.get("reasoning_submitted"):
        st.success("Your reasoning has been recorded and evaluated internally.")
        render_feedback_and_revision()


def render_feedback_and_revision() -> None:
    """Display first-level feedback and let the learner request help or revise."""
    feedback_items = st.session_state.get("reasoning_feedback", [])
    evaluation = st.session_state.get("reasoning_evaluation", {})
    attempt = st.session_state.get("completed_reasoning_attempt", {})

    for index, item in enumerate(feedback_items):
        st.info(item["message"])
        if item["hint_level"] < MAX_HINT_LEVEL:
            label = "Show Hint" if item["hint_level"] == 1 else "Show Explanation"
            if st.button(label, key=f"hint_{index}_{item['step']}"):
                next_level = item["hint_level"] + 1
                updated = get_hint(
                    evaluation,
                    item["step"],
                    next_level,
                    item["issue_type"],
                ).to_dict()
                feedback_items[index] = updated
                st.session_state.reasoning_feedback = feedback_items
                st.rerun()

        if st.button("Revise My Reasoning", key=f"revise_{index}_{item['step']}"):
            history = st.session_state.get("reasoning_attempt_history", [])
            history.append(
                {
                    "attempt": deepcopy(attempt),
                    "evaluation": deepcopy(evaluation),
                    "feedback": deepcopy(feedback_items),
                }
            )
            st.session_state.reasoning_attempt_history = history
            st.session_state.reasoning_draft = deepcopy(attempt)
            st.session_state.reasoning_step = _step_index(item["step"])
            st.session_state.reasoning_submitted = False
            st.session_state.reasoning_feedback = []
            st.rerun()


def _step_index(step: str) -> int:
    """Map an evaluation step name to its learner workflow position."""
    for index, (_, field) in enumerate(STEPS):
        if field == step:
            return index
    return len(STEPS) - 2


def _validate_current_step(draft: dict[str, Any], field: str) -> list[str]:
    if field in FINDING_FIELDS:
        section = draft[field]
        labels = {
            "rate": "ventricular rate",
            "rhythm": "rhythm",
            "axis": "cardiac axis",
            "p_waves": "P waves",
            "pr_interval": "PR interval",
            "qrs": "QRS complex",
            "st_t": "ST/T findings",
        }
        if not str(section.get("answer", "")).strip():
            return [f"Please provide your {labels[field]} observation."]
        if not str(section.get("reasoning", "")).strip():
            return [f"Please explain your reasoning for {labels[field]}."]
    elif field == "interpretation" and not draft[field].strip():
        return ["Please provide your overall interpretation."]
    elif field == "overall_reasoning" and not draft[field].strip():
        return ["Please provide your overall reasoning."]
    elif field == "confidence":
        confidence = draft.get("confidence")
        if isinstance(confidence, bool) or not isinstance(confidence, int) or not 1 <= confidence <= 5:
            return ["Please select a confidence level from 1 to 5."]
    return []
