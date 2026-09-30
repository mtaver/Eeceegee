"""Load and retrieve educational ECG case data."""

import json
from pathlib import Path
from typing import Any


CASES_FILE = Path(__file__).resolve().parent.parent / "data" / "cases.json"


def load_cases() -> list[dict[str, Any]]:
    """Load cases from the JSON file, returning an empty list for invalid data."""
    try:
        with CASES_FILE.open(encoding="utf-8") as case_file:
            data = json.load(case_file)
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(data, list):
        return []
    return [case for case in data if isinstance(case, dict)]


def get_cases_by_difficulty(difficulty: str) -> list[dict[str, Any]]:
    """Return cases whose difficulty matches the supplied value."""
    return [case for case in load_cases() if case.get("difficulty") == difficulty]


def get_case_by_id(case_id: str) -> dict[str, Any] | None:
    """Return the matching case, or None when no such case exists."""
    return next((case for case in load_cases() if case.get("id") == case_id), None)
