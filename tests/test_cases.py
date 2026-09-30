"""Tests for educational case loading and retrieval."""

from services.case_manager import (
    get_case_by_id,
    get_cases_by_difficulty,
    load_cases,
)


def test_cases_load_correctly():
    cases = load_cases()
    assert isinstance(cases, list)
    assert all(isinstance(case, dict) for case in cases)


def test_at_least_one_case_exists():
    assert load_cases()


def test_filtering_by_difficulty_works():
    cases = get_cases_by_difficulty("Beginner")
    assert cases
    assert all(case["difficulty"] == "Beginner" for case in cases)


def test_retrieving_case_by_id_works():
    case = get_case_by_id("case_001")
    assert case is not None
    assert case["title"] == "Basic Rhythm Recognition"


def test_nonexistent_case_returns_none():
    assert get_case_by_id("missing_case") is None
