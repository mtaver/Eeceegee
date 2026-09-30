"""Session-friendly progress tracking derived from learner reasoning evidence."""

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, MutableMapping

from services.reasoning import FINDING_FIELDS


PROGRESS_STEPS = (*FINDING_FIELDS, "interpretation", "overall_reasoning")
RECENT_ATTEMPT_LIMIT = 20
STRONG_REASONING_QUALITY = {"strong", "adequate"}
WEAK_REASONING_QUALITY = {"weak", "missing", "contradictory"}


@dataclass
class StepStatistic:
    step: str
    attempts: int = 0
    issues: int = 0
    revisions: int = 0
    resolved_issues: int = 0
    strong_reasoning: int = 0
    weak_reasoning: int = 0
    recurring_problems: dict[str, int] = field(default_factory=dict)


@dataclass
class LearnerProgress:
    total_cases_started: int = 0
    total_cases_completed: int = 0
    total_attempts: int = 0
    total_revisions: int = 0
    average_confidence: float | None = None
    reasoning_strengths: list[str] = field(default_factory=list)
    reasoning_weaknesses: list[str] = field(default_factory=list)
    step_statistics: dict[str, StepStatistic] = field(default_factory=dict)
    recent_attempts: list[dict[str, Any]] = field(default_factory=list)
    cases_started: list[str] = field(default_factory=list)
    cases_completed: list[str] = field(default_factory=list)
    confidence_total: int = 0
    confidence_count: int = 0
    hints_requested: int = 0
    hint_level_total: int = 0
    feedback_issues_addressed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def create_progress() -> dict[str, Any]:
    """Return a new empty, serializable learner progress record."""
    progress = LearnerProgress(
        step_statistics={step: StepStatistic(step) for step in PROGRESS_STEPS}
    )
    return progress.to_dict()


def initialize_progress_session(session_state: MutableMapping[str, Any]) -> None:
    """Initialize session storage without overwriting existing learner data."""
    session_state.setdefault("progress", create_progress())
    session_state.setdefault("attempt_history", [])


def _ensure_progress(progress: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    defaults = create_progress()
    for key, value in defaults.items():
        if key not in progress:
            progress[key] = deepcopy(value)
    for step in PROGRESS_STEPS:
        progress["step_statistics"].setdefault(step, asdict(StepStatistic(step)))
    return progress


def record_case_started(progress: MutableMapping[str, Any], case_id: str) -> None:
    """Count each distinct educational case once as started."""
    _ensure_progress(progress)
    if isinstance(case_id, str) and case_id and case_id not in progress["cases_started"]:
        progress["cases_started"].append(case_id)
        progress["total_cases_started"] += 1


def _evaluation_dict(evaluation: Any) -> dict[str, Any]:
    if hasattr(evaluation, "to_dict"):
        evaluation = evaluation.to_dict()
    elif hasattr(evaluation, "__dataclass_fields__"):
        evaluation = asdict(evaluation)
    return deepcopy(evaluation) if isinstance(evaluation, dict) else {}


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _issues_by_step(evaluation: dict[str, Any]) -> dict[str, set[str]]:
    issues: dict[str, set[str]] = {step: set() for step in PROGRESS_STEPS}
    for item in evaluation.get("step_results", []):
        if not isinstance(item, dict):
            continue
        step = item.get("step")
        if step not in issues:
            continue
        status = _enum_value(item.get("status", ""))
        if status in {"missing", "incorrect", "partially_correct"}:
            issues[step].add(status)
        for issue in item.get("issues", []) or []:
            if isinstance(issue, dict) and issue.get("type"):
                issues[step].add(str(issue["type"]))
    for issue in evaluation.get("contradictions", []) or []:
        if isinstance(issue, dict):
            for step in issue.get("steps", []):
                if step in issues:
                    issues[step].add(str(issue.get("type", "reasoning_contradiction")))
    for issue in evaluation.get("reasoning_issues", []) or []:
        if isinstance(issue, dict):
            steps = issue.get("steps", []) or ["overall_reasoning"]
            for step in steps:
                if step in issues:
                    issues[step].add(str(issue.get("type", "reasoning_issue")))
    return issues


def _quality_by_step(evaluation: dict[str, Any]) -> dict[str, str]:
    qualities = {step: "not_evaluated" for step in PROGRESS_STEPS}
    for item in evaluation.get("step_results", []) or []:
        if isinstance(item, dict) and item.get("step") in qualities:
            qualities[item["step"]] = _enum_value(item.get("reasoning_quality", "not_evaluated"))
    for issue in evaluation.get("contradictions", []) or []:
        if isinstance(issue, dict):
            for step in issue.get("steps", []):
                if step in qualities:
                    qualities[step] = "contradictory"
    for issue in evaluation.get("reasoning_issues", []) or []:
        if isinstance(issue, dict) and issue.get("type") in WEAK_REASONING_QUALITY:
            for step in issue.get("steps", []) or ["overall_reasoning"]:
                if step in qualities:
                    qualities[step] = "missing" if issue["type"] == "missing_reasoning" else "weak"
    return qualities


def _feedback_snapshot(feedback: Any) -> list[dict[str, Any]]:
    if not isinstance(feedback, (list, tuple)):
        return []
    snapshots = []
    for item in feedback:
        if hasattr(item, "to_dict"):
            item = item.to_dict()
        elif hasattr(item, "__dataclass_fields__"):
            item = asdict(item)
        if isinstance(item, dict):
            # Keep only learner-facing feedback fields. Reference data is never copied.
            snapshots.append(
                {
                    key: deepcopy(item[key])
                    for key in ("step", "severity", "issue_type", "message", "hint_level", "next_action")
                    if key in item
                }
            )
    return snapshots


def _response_snapshot(attempt: Any) -> dict[str, Any]:
    if not isinstance(attempt, dict):
        return {}
    allowed = (*PROGRESS_STEPS, "case_id", "overall_reasoning", "confidence")
    return {key: deepcopy(attempt[key]) for key in allowed if key in attempt}


def _update_strengths_and_weaknesses(progress: MutableMapping[str, Any]) -> None:
    strengths: list[str] = []
    weaknesses: list[str] = []
    for step, raw_stat in progress["step_statistics"].items():
        stat = raw_stat if isinstance(raw_stat, dict) else asdict(raw_stat)
        label = "P waves" if step == "p_waves" else "PR interval" if step == "pr_interval" else step.replace("_", " ").title()
        if stat["strong_reasoning"] >= 2 and stat["strong_reasoning"] > stat["weak_reasoning"]:
            strengths.append(f"{label} reasoning")
        if stat["issues"] >= 2 and stat["issues"] >= stat["attempts"] / 2:
            weaknesses.append(f"{label} reasoning")
    progress["reasoning_strengths"] = strengths
    progress["reasoning_weaknesses"] = weaknesses


def record_attempt(
    progress: MutableMapping[str, Any],
    attempt: dict[str, Any],
    evaluation: Any,
    feedback: Any = None,
    *,
    timestamp: str | None = None,
    attempt_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Record a submission and update evidence-based learner progress."""
    _ensure_progress(progress)
    evaluation_data = _evaluation_dict(evaluation)
    feedback_data = _feedback_snapshot(feedback)
    case_id = str(attempt.get("case_id", evaluation_data.get("case_id", "")))
    case_attempts = [item for item in progress["recent_attempts"] if item.get("case_id") == case_id]
    if attempt_history is not None:
        case_attempts = [item for item in attempt_history if item.get("case_id") == case_id]
    attempt_number = 1 + max((int(item.get("attempt_number", 0)) for item in case_attempts), default=0)
    recorded_at = timestamp or datetime.now(timezone.utc).isoformat()
    current_issues = _issues_by_step(evaluation_data)
    previous = case_attempts[-1] if case_attempts else None
    resolved: dict[str, list[str]] = {}
    if previous and previous.get("revised"):
        for step, old_issues in previous.get("issues_by_step", {}).items():
            new_issues = current_issues.get(step, set())
            resolved_for_step = sorted(set(old_issues) - new_issues)
            if resolved_for_step:
                resolved[step] = resolved_for_step
                progress["feedback_issues_addressed"] += len(resolved_for_step)

    confidence = attempt.get("confidence")
    if isinstance(confidence, int) and not isinstance(confidence, bool) and 1 <= confidence <= 5:
        progress["confidence_total"] += confidence
        progress["confidence_count"] += 1
        progress["average_confidence"] = round(
            progress["confidence_total"] / progress["confidence_count"], 2
        )

    quality = _quality_by_step(evaluation_data)
    for step in PROGRESS_STEPS:
        stat = progress["step_statistics"][step]
        stat["attempts"] += 1
        if current_issues[step]:
            stat["issues"] += len(current_issues[step])
            for issue in current_issues[step]:
                stat["recurring_problems"][issue] = stat["recurring_problems"].get(issue, 0) + 1
        if quality[step] in STRONG_REASONING_QUALITY:
            stat["strong_reasoning"] += 1
        elif quality[step] in WEAK_REASONING_QUALITY:
            stat["weak_reasoning"] += 1
        stat["resolved_issues"] += len(resolved.get(step, []))

    if case_id and case_id not in progress["cases_completed"]:
        progress["cases_completed"].append(case_id)
        progress["total_cases_completed"] += 1
    progress["total_attempts"] += 1
    record = {
        "case_id": case_id,
        "timestamp": recorded_at,
        "confidence": confidence,
        "evaluation_summary": {
            "overall_status": _enum_value(evaluation_data.get("overall_status", "not_evaluated")),
            "issues_by_step": {step: sorted(values) for step, values in current_issues.items()},
            "reasoning_quality_by_step": quality,
        },
        "feedback": feedback_data,
        "hint_levels_used": [],
        "hints_requested": 0,
        "revised": False,
        "attempt_number": attempt_number,
        "responses": _response_snapshot(attempt),
        "issues_by_step": {step: sorted(values) for step, values in current_issues.items()},
        "resolved_issues": resolved,
    }
    history = attempt_history if attempt_history is not None else progress["recent_attempts"]
    history.append(record)
    if history is progress["recent_attempts"]:
        del history[:-RECENT_ATTEMPT_LIMIT]
    else:
        progress["recent_attempts"].append(deepcopy(record))
        del progress["recent_attempts"][:-RECENT_ATTEMPT_LIMIT]
    _update_strengths_and_weaknesses(progress)
    return record


def record_revision(progress: MutableMapping[str, Any], attempt_record: dict[str, Any]) -> None:
    """Mark a submitted attempt as revised and count revisions once."""
    _ensure_progress(progress)
    if attempt_record.get("revised"):
        return
    attempt_record["revised"] = True
    progress["total_revisions"] += 1
    for step, stat in progress["step_statistics"].items():
        if attempt_record.get("issues_by_step", {}).get(step):
            stat["revisions"] += 1
    for snapshot in progress["recent_attempts"]:
        if snapshot.get("timestamp") == attempt_record.get("timestamp"):
            snapshot["revised"] = True


def record_hint_usage(
    progress: MutableMapping[str, Any],
    attempt_record: dict[str, Any],
    step: str,
    hint_level: int,
) -> None:
    """Record an explicitly requested hint and its level."""
    _ensure_progress(progress)
    if not isinstance(hint_level, int) or isinstance(hint_level, bool) or not 1 <= hint_level <= 3:
        return
    attempt_record["hints_requested"] = int(attempt_record.get("hints_requested", 0)) + 1
    attempt_record.setdefault("hint_levels_used", []).append(
        {"step": step, "level": hint_level}
    )
    progress["hints_requested"] += 1
    progress["hint_level_total"] += hint_level
    for snapshot in progress["recent_attempts"]:
        if snapshot.get("timestamp") == attempt_record.get("timestamp"):
            snapshot["hints_requested"] = attempt_record["hints_requested"]
            snapshot["hint_levels_used"] = deepcopy(attempt_record["hint_levels_used"])


def update_progress(progress: MutableMapping[str, Any], **updates: Any) -> None:
    """Apply supported case/session counters without overwriting derived evidence."""
    _ensure_progress(progress)
    for key in ("total_cases_started", "total_cases_completed"):
        if key in updates and isinstance(updates[key], int) and updates[key] >= progress[key]:
            progress[key] = updates[key]


def get_step_statistics(progress: MutableMapping[str, Any]) -> dict[str, dict[str, Any]]:
    _ensure_progress(progress)
    return deepcopy(progress["step_statistics"])


def get_recent_attempts(progress: MutableMapping[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    _ensure_progress(progress)
    safe_limit = max(0, int(limit))
    return deepcopy(list(reversed(progress["recent_attempts"][-safe_limit:]))) if safe_limit else []


def get_progress_summary(progress: MutableMapping[str, Any] | None) -> dict[str, Any]:
    """Return a learner-facing progress summary without case reference data."""
    if not isinstance(progress, MutableMapping):
        progress = create_progress()
    _ensure_progress(progress)
    recent = get_recent_attempts(progress)
    recent_improvements = []
    confidence_reasoning_patterns: list[str] = []
    for record in recent:
        for step, issues in record.get("resolved_issues", {}).items():
            recent_improvements.append(
                {
                    "case_id": record["case_id"],
                    "step": step,
                    "resolved_issues": list(issues),
                    "message": f"You resolved a {step.replace('_', ' ')} reasoning issue identified in an earlier attempt.",
                }
            )
        confidence = record.get("confidence")
        quality_values = set(record.get("evaluation_summary", {}).get("reasoning_quality_by_step", {}).values())
        if isinstance(confidence, int) and confidence >= 4 and quality_values & WEAK_REASONING_QUALITY:
            message = "Confidence was high while reasoning evidence was limited."
            if message not in confidence_reasoning_patterns:
                confidence_reasoning_patterns.append(message)
        elif isinstance(confidence, int) and confidence <= 2 and quality_values & STRONG_REASONING_QUALITY:
            message = "Confidence was low while reasoning evidence was well-supported."
            if message not in confidence_reasoning_patterns:
                confidence_reasoning_patterns.append(message)
    return {
        "cases_started": progress["total_cases_started"],
        "cases_completed": progress["total_cases_completed"],
        "attempts": progress["total_attempts"],
        "revisions": progress["total_revisions"],
        "average_confidence": progress["average_confidence"],
        "top_strengths": list(progress["reasoning_strengths"]),
        "areas_for_practice": list(progress["reasoning_weaknesses"]),
        "recent_improvements": recent_improvements,
        "confidence_reasoning_patterns": confidence_reasoning_patterns,
        "step_statistics": get_step_statistics(progress),
        "hints_requested": progress["hints_requested"],
        "average_hint_level": (
            round(progress["hint_level_total"] / progress["hints_requested"], 2)
            if progress["hints_requested"]
            else None
        ),
        "feedback_issues_addressed": progress["feedback_issues_addressed"],
        "recent_attempts": recent,
    }
