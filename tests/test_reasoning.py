"""Tests for the Streamlit-independent student reasoning model."""

import pytest

from services.reasoning import (
    FINDING_FIELDS,
    create_reasoning_attempt,
    set_confidence,
    validate_reasoning_attempt,
)


def test_new_attempt_has_expected_structure():
    attempt = create_reasoning_attempt("case_001")
    assert attempt["case_id"] == "case_001"
    assert all(attempt[field] == {"answer": "", "reasoning": ""} for field in FINDING_FIELDS)
    assert attempt["interpretation"] == ""
    assert attempt["overall_reasoning"] == ""
    assert attempt["confidence"] is None


def test_each_reasoning_section_exists():
    attempt = create_reasoning_attempt("case_001")
    assert set(FINDING_FIELDS).issubset(attempt)


def test_answers_and_reasoning_text_can_be_stored():
    attempt = create_reasoning_attempt("case_001")
    attempt["rate"]["answer"] = "72 bpm"
    attempt["rate"]["reasoning"] = "Estimated using the large-square method."
    assert attempt["rate"] == {
        "answer": "72 bpm",
        "reasoning": "Estimated using the large-square method.",
    }


@pytest.mark.parametrize("confidence", [1, 2, 3, 4, 5])
def test_confidence_accepts_values_one_through_five(confidence):
    attempt = create_reasoning_attempt("case_001")
    set_confidence(attempt, confidence)
    assert attempt["confidence"] == confidence


@pytest.mark.parametrize("confidence", [0, 6, -1, 2.5, "4", True, None])
def test_invalid_confidence_values_are_rejected(confidence):
    attempt = create_reasoning_attempt("case_001")
    with pytest.raises(ValueError):
        set_confidence(attempt, confidence)


def test_completed_attempt_contains_case_and_final_reasoning():
    attempt = create_reasoning_attempt("case_001")
    for field in FINDING_FIELDS:
        attempt[field]["answer"] = f"Observation for {field}"
        attempt[field]["reasoning"] = f"Reasoning for {field}"
    attempt["interpretation"] = "Learner's own interpretation"
    attempt["overall_reasoning"] = "Learner's explanation of their conclusion"
    set_confidence(attempt, 4)

    assert attempt["case_id"] == "case_001"
    assert attempt["interpretation"] == "Learner's own interpretation"
    assert attempt["overall_reasoning"] == "Learner's explanation of their conclusion"
    assert validate_reasoning_attempt(attempt) == []


def test_empty_attempt_has_missing_response_errors():
    errors = validate_reasoning_attempt(create_reasoning_attempt("case_001"))
    assert errors
    assert any("ventricular rate" in error for error in errors)


def test_case_id_is_required():
    with pytest.raises(ValueError):
        create_reasoning_attempt(" ")
