"""Tests for educational case loading and learner-safe retrieval."""

from services.case_manager import (
    REQUIRED_CASE_FIELDS,
    get_available_difficulties,
    get_case_by_id,
    get_case_for_student,
    get_cases_by_difficulty,
    load_cases,
)


def test_all_cases_load():
    cases = load_cases()
    assert isinstance(cases, list)
    assert all(isinstance(case, dict) for case in cases)


def test_case_count_is_five():
    assert len(load_cases()) == 5


def test_available_difficulties():
    assert get_available_difficulties() == ["Beginner", "Intermediate", "Advanced"]


def test_filtering_by_beginner():
    cases = get_cases_by_difficulty("Beginner")
    assert len(cases) == 2
    assert all(case["difficulty"] == "Beginner" for case in cases)


def test_filtering_by_intermediate():
    cases = get_cases_by_difficulty("Intermediate")
    assert len(cases) == 2
    assert all(case["difficulty"] == "Intermediate" for case in cases)


def test_filtering_by_advanced():
    cases = get_cases_by_difficulty("Advanced")
    assert len(cases) == 1
    assert all(case["difficulty"] == "Advanced" for case in cases)


def test_difficulty_filter_is_case_insensitive_and_validated():
    assert get_cases_by_difficulty(" beginner ") == get_cases_by_difficulty("Beginner")
    assert get_cases_by_difficulty("") == []
    assert get_cases_by_difficulty(None) == []


def test_retrieving_existing_case():
    case = get_case_by_id("case_001")
    assert case is not None
    assert case["title"] == "Rate and Rhythm Fundamentals"


def test_nonexistent_or_invalid_case_id_returns_none():
    assert get_case_by_id("missing_case") is None
    assert get_case_by_id("") is None
    assert get_case_by_id(None) is None


def test_every_case_has_required_fields():
    cases = load_cases()
    assert cases
    for case in cases:
        assert REQUIRED_CASE_FIELDS.issubset(case)
        assert isinstance(case["learning_objectives"], list)
        assert isinstance(case["reference_findings"], dict)


def test_student_case_does_not_expose_reference_information():
    case = get_case_for_student("case_001")
    assert case is not None
    assert set(case) == {
        "id",
        "title",
        "difficulty",
        "description",
        "learning_objectives",
        "ecg_image",
    }
    assert "reference_findings" not in case
    assert "reference_interpretation" not in case
    assert get_case_for_student("missing_case") is None
