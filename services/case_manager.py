"""Load, validate, and safely present educational ECG case data."""

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


CASES_FILE = Path(__file__).resolve().parent.parent / "data" / "cases.json"
REFERENCE_DOMAINS = (
    "rate",
    "rhythm",
    "axis",
    "p_waves",
    "pr_interval",
    "qrs",
    "st_t",
)
REQUIRED_CASE_FIELDS = {
    "case_id",
    "title",
    "learner_title",
    "difficulty",
    "description",
    "learning_objectives",
    "image_path",
    "source_name",
    "source_url",
    "license",
    "source_record",
    "reference_findings",
    "reference_interpretation",
    "teaching_notes",
}
STUDENT_CASE_FIELDS = (
    "case_id",
    "difficulty",
    "description",
    "learning_objectives",
    "image_path",
    "source_name",
    "source_url",
    "license",
    "source_record",
)


def validate_case(case: Any) -> bool:
    """Return whether a case has the supported schema and field types."""
    if not isinstance(case, dict) or not REQUIRED_CASE_FIELDS.issubset(case):
        return False
    for field in (
        "case_id",
        "title",
        "learner_title",
        "difficulty",
        "description",
        "reference_interpretation",
        "teaching_notes",
    ):
        if not isinstance(case[field], str) or not case[field].strip():
            return False
    if not isinstance(case["learning_objectives"], list) or not case["learning_objectives"]:
        return False
    if not all(isinstance(item, str) and item.strip() for item in case["learning_objectives"]):
        return False
    image_path = case["image_path"]
    if image_path is not None and not _is_safe_ecg_image_path(image_path):
        return False
    for field in ("source_name", "source_url", "license", "source_record"):
        if case[field] is not None and (not isinstance(case[field], str) or not case[field].strip()):
            return False
    if case["source_url"] is not None:
        parsed_url = urlparse(case["source_url"])
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            return False
    if image_path is not None and not all(case[field] for field in ("source_name", "source_url", "license", "source_record")):
        return False

    findings = case["reference_findings"]
    if not isinstance(findings, dict) or not set(REFERENCE_DOMAINS).issubset(findings):
        return False
    for domain in REFERENCE_DOMAINS:
        value = findings[domain]
        if isinstance(value, str):
            continue  # Empty strings remain valid for cases without usable references.
        if not isinstance(value, dict):
            return False
        if "answer" in value and not isinstance(value["answer"], (str, int, float, list)):
            return False
    return True


def _is_safe_ecg_image_path(image_path: Any) -> bool:
    """Accept only relative local assets located beneath assets/ecg/."""
    if not isinstance(image_path, str) or not image_path.strip() or "\\" in image_path:
        return False
    candidate = Path(image_path)
    return (
        not candidate.is_absolute()
        and not candidate.drive
        and len(candidate.parts) >= 3
        and candidate.parts[0:2] == ("assets", "ecg")
        and all(part not in {".", ".."} for part in candidate.parts)
    )


def resolve_ecg_image_path(image_path: Any) -> Path | None:
    """Resolve a schema-safe case image path to an existing local file."""
    if not _is_safe_ecg_image_path(image_path):
        return None
    project_root = CASES_FILE.parent.parent.resolve()
    resolved = (project_root / image_path).resolve()
    try:
        resolved.relative_to((project_root / "assets" / "ecg").resolve())
    except ValueError:
        return None
    return resolved if resolved.is_file() else None


def load_cases() -> list[dict[str, Any]]:
    """Load schema-valid case records, returning an empty list for invalid data."""
    try:
        with CASES_FILE.open(encoding="utf-8") as case_file:
            data = json.load(case_file)
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(data, list):
        return []

    cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in data:
        if not validate_case(item) or item["case_id"] in seen_ids:
            continue
        case = dict(item)
        # Keep the existing app contract while case_id remains canonical in JSON.
        case["id"] = case["case_id"]
        cases.append(case)
        seen_ids.add(case["case_id"])
    return cases


def get_cases_by_difficulty(difficulty: str) -> list[dict[str, Any]]:
    """Return cases whose difficulty matches a non-empty label."""
    if not isinstance(difficulty, str) or not difficulty.strip():
        return []
    normalized_difficulty = difficulty.strip().casefold()
    return [
        case
        for case in load_cases()
        if case["difficulty"].casefold() == normalized_difficulty
    ]


def get_case_by_id(case_id: str) -> dict[str, Any] | None:
    """Return a complete internal case by canonical case ID, or None."""
    if not isinstance(case_id, str) or not case_id.strip():
        return None
    normalized_id = case_id.strip()
    return next((case for case in load_cases() if case["case_id"] == normalized_id), None)


def get_available_difficulties() -> list[str]:
    """Return unique difficulty labels in data order."""
    difficulties: list[str] = []
    for case in load_cases():
        difficulty = case["difficulty"]
        if difficulty not in difficulties:
            difficulties.append(difficulty)
    return difficulties


def get_case_for_student(case_id: str) -> dict[str, Any] | None:
    """Return learner-safe case presentation fields only."""
    case = get_case_by_id(case_id)
    if case is None:
        return None
    student_case = {field: case[field] for field in STUDENT_CASE_FIELDS}
    student_case["id"] = case["case_id"]  # Backward-compatible UI identifier.
    student_case["title"] = case["learner_title"]
    return student_case


def get_learner_case_labels(cases: list[dict[str, Any]]) -> dict[str, str]:
    """Return neutral learner-facing selector labels keyed by internal case ID."""
    return {
        case["case_id"]: case["learner_title"]
        for case in cases
        if isinstance(case, dict)
        and isinstance(case.get("case_id"), str)
        and isinstance(case.get("learner_title"), str)
    }
