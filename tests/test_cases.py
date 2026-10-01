"""Tests for structured case loading and learner-safe retrieval."""

from services.case_manager import (
    REFERENCE_DOMAINS,
    REQUIRED_CASE_FIELDS,
    get_available_difficulties,
    get_case_by_id,
    get_case_for_student,
    get_cases_by_difficulty,
    load_cases,
    validate_case,
)
from services.evaluator import EvaluationStatus, evaluate_interpretation, evaluate_rate


EXPECTED_CASES = {
    "case_001": "Normal Sinus Rhythm",
    "case_002": "Sinus Bradycardia",
    "case_003": "Sinus Tachycardia",
}


def test_all_three_cases_load_with_valid_schema():
    cases = load_cases()
    assert len(cases) == 3
    assert {case["case_id"]: case["title"] for case in cases} == EXPECTED_CASES
    for case in cases:
        assert validate_case(case)
        assert REQUIRED_CASE_FIELDS.issubset(case)
        assert set(case["reference_findings"]) == set(REFERENCE_DOMAINS)
        assert all(isinstance(case["reference_findings"][domain], dict) for domain in REFERENCE_DOMAINS)


def test_difficulty_filters_match_new_case_set():
    assert get_available_difficulties() == ["Beginner", "Intermediate"]
    assert len(get_cases_by_difficulty("Beginner")) == 1
    assert len(get_cases_by_difficulty("Intermediate")) == 2
    assert get_cases_by_difficulty(" beginner ") == get_cases_by_difficulty("Beginner")
    assert get_cases_by_difficulty("") == []
    assert get_cases_by_difficulty(None) == []


def test_retrieving_existing_and_missing_cases():
    case = get_case_by_id("case_001")
    assert case is not None
    assert case["title"] == "Normal Sinus Rhythm"
    assert case["id"] == case["case_id"]
    assert get_case_by_id("missing_case") is None
    assert get_case_by_id("") is None
    assert get_case_by_id(None) is None


def test_invalid_schema_is_rejected():
    case = get_case_by_id("case_001")
    assert case is not None
    case["reference_findings"] = {"rate": {"answer": "75"}}
    assert not validate_case(case)


def test_student_projection_excludes_all_reference_material():
    case = get_case_for_student("case_001")
    assert case is not None
    assert set(case) == {
        "id",
        "case_id",
        "title",
        "difficulty",
        "description",
        "learning_objectives",
        "ecg_image",
    }
    assert case["title"] != "Normal Sinus Rhythm"
    assert "reference_findings" not in case
    assert "reference_interpretation" not in case
    assert "teaching_notes" not in case
    assert get_case_for_student("missing_case") is None


def test_reference_data_remains_available_to_evaluator_only_internally():
    case = get_case_by_id("case_001")
    learner_case = get_case_for_student("case_001")
    assert case is not None and learner_case is not None
    assert evaluate_rate({"answer": "75", "reasoning": "Counted ventricular complexes"}, case).status == EvaluationStatus.CORRECT
    assert evaluate_interpretation("Normal sinus rhythm", case).status == EvaluationStatus.CORRECT
    assert evaluate_rate({"answer": "75", "reasoning": "Counted ventricular complexes"}, learner_case).status == EvaluationStatus.NOT_EVALUATED
    assert evaluate_interpretation("Normal sinus rhythm", learner_case).status == EvaluationStatus.NOT_EVALUATED
