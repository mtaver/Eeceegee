"""Load, validate, and safely present educational ECG case data."""

import json
from pathlib import Path
from typing import Any


CASES_FILE = Path(__file__).resolve().parent.parent / "data" / "cases.json"
REQUIRED_CASE_FIELDS = {
    "id",
    "title",
    "difficulty",
    "description",
    "learning_objectives",
    "ecg_image",
    "reference_findings",
    "reference_interpretation",
}
STUDENT_CASE_FIELDS = (
    "id",
    "title",
    "difficulty",
    "description",
    "learning_objectives",
    "ecg_image",
)


def load_cases() -> list[dict[str, Any]]:
    """Load valid case records, returning an empty list for unusable data."""
    try:
        with CASES_FILE.open(encoding="utf-8") as case_file:
            data = json.load(case_file)
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(data, list):
        return []

    return [
        case
        for case in data
        if isinstance(case, dict) and REQUIRED_CASE_FIELDS.issubset(case)
    ]


def get_cases_by_difficulty(difficulty: str) -> list[dict[str, Any]]:
    """Return cases matching a non-empty difficulty label."""
    if not isinstance(difficulty, str) or not difficulty.strip():
        return []
    normalized_difficulty = difficulty.strip().casefold()
    return [
        case
        for case in load_cases()
        if case["difficulty"].casefold() == normalized_difficulty
    ]


def get_case_by_id(case_id: str) -> dict[str, Any] | None:
    """Return a complete case by ID, or None for invalid or unknown IDs."""
    if not isinstance(case_id, str) or not case_id.strip():
        return None
    normalized_id = case_id.strip()
    return next((case for case in load_cases() if case["id"] == normalized_id), None)


def get_available_difficulties() -> list[str]:
    """Return unique difficulty labels in the order they appear in the data."""
    difficulties: list[str] = []
    for case in load_cases():
        difficulty = case["difficulty"]
        if isinstance(difficulty, str) and difficulty not in difficulties:
            difficulties.append(difficulty)
    return difficulties


def get_case_for_student(case_id: str) -> dict[str, Any] | None:
    """Return only case presentation fields, excluding reference answers."""
    case = get_case_by_id(case_id)
    if case is None:
        return None
    return {field: case[field] for field in STUDENT_CASE_FIELDS}
