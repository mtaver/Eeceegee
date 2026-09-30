"""Data model and validation for structured student ECG reasoning."""

from typing import Any, MutableMapping


FINDING_FIELDS = (
    "rate",
    "rhythm",
    "axis",
    "p_waves",
    "pr_interval",
    "qrs",
    "st_t",
)


def coerce_numeric_value(value: Any) -> int | float | None:
    """Convert persisted numeric input to a widget-safe number or None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            numeric_value = float(value)
        except ValueError:
            return None
        return int(numeric_value) if numeric_value.is_integer() else numeric_value
    return None


def normalize_rate_widget_state(
    session_state: MutableMapping[str, Any],
    persisted_answer: Any = None,
) -> int | float | None:
    """Normalize the keyed Streamlit value before its number_input is rendered."""
    widget_key = "reasoning_rate_answer"
    raw_value = session_state.get(widget_key, persisted_answer)
    numeric_value = coerce_numeric_value(raw_value)
    if numeric_value is None and raw_value not in (None, ""):
        persisted_value = coerce_numeric_value(persisted_answer)
        if persisted_value is not None:
            session_state[widget_key] = persisted_value
            return persisted_value
        session_state.pop(widget_key, None)
    elif widget_key in session_state or numeric_value is not None:
        session_state[widget_key] = numeric_value
    return numeric_value


def create_reasoning_attempt(case_id: str) -> dict[str, Any]:
    """Create an empty reasoning attempt for a case."""
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("case_id must be a non-empty string")
    attempt: dict[str, Any] = {"case_id": case_id.strip()}
    attempt.update({field: {"answer": "", "reasoning": ""} for field in FINDING_FIELDS})
    attempt.update(
        {
            "interpretation": "",
            "overall_reasoning": "",
            "confidence": None,
        }
    )
    return attempt


def set_confidence(attempt: dict[str, Any], confidence: int) -> None:
    """Set confidence to an integer on the learner's 1–5 scale."""
    if isinstance(confidence, bool) or not isinstance(confidence, int):
        raise ValueError("confidence must be an integer from 1 to 5")
    if not 1 <= confidence <= 5:
        raise ValueError("confidence must be an integer from 1 to 5")
    attempt["confidence"] = confidence


def validate_reasoning_attempt(attempt: dict[str, Any]) -> list[str]:
    """Return missing required responses; this does not assess correctness."""
    errors: list[str] = []
    if not isinstance(attempt.get("case_id"), str) or not attempt["case_id"].strip():
        errors.append("A case is required.")

    labels = {
        "rate": "ventricular rate",
        "rhythm": "rhythm",
        "axis": "cardiac axis",
        "p_waves": "P waves",
        "pr_interval": "PR interval",
        "qrs": "QRS complex",
        "st_t": "ST/T findings",
    }
    for field, label in labels.items():
        section = attempt.get(field)
        if not isinstance(section, dict):
            errors.append(f"Please complete the {label} step.")
            continue
        if not isinstance(section.get("answer"), str) or not section["answer"].strip():
            errors.append(f"Please provide your {label} observation.")
        if not isinstance(section.get("reasoning"), str) or not section["reasoning"].strip():
            errors.append(f"Please explain your reasoning for {label}.")

    for field, prompt in (
        ("interpretation", "overall interpretation"),
        ("overall_reasoning", "overall reasoning"),
    ):
        if not isinstance(attempt.get(field), str) or not attempt[field].strip():
            errors.append(f"Please provide your {prompt}.")

    confidence = attempt.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, int) or not 1 <= confidence <= 5:
        errors.append("Please select a confidence level from 1 to 5.")
    return errors
