"""Rule-based Socratic feedback for ECG reasoning evaluations."""

from dataclasses import asdict, dataclass
from enum import Enum, IntEnum
from typing import Any, Mapping


class HintLevel(IntEnum):
    GUIDING_QUESTION = 1
    SPECIFIC_HINT = 2
    EXPLANATION = 3


class FeedbackSeverity(str, Enum):
    ATTENTION = "attention"
    SUGGESTION = "suggestion"
    INFORMATION = "information"


class NextAction(str, Enum):
    RECHECK_RR_INTERVALS = "recheck_rr_intervals"
    ADD_REASONING = "add_reasoning"
    REVIEW_OBSERVATION = "review_observation"
    EXPLAIN_EVIDENCE = "explain_evidence"
    REFLECT_ON_FINDINGS = "reflect_on_findings"


MAX_FEEDBACK_ITEMS = 3
MAX_HINT_LEVEL = 3


@dataclass(frozen=True)
class FeedbackItem:
    step: str
    severity: FeedbackSeverity
    issue_type: str
    message: str
    hint_level: int
    next_action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_QUESTIONS = {
    "rate": "What features of the ECG did you use to estimate the ventricular rate?",
    "rhythm": "Compare the R–R intervals across several consecutive beats. What pattern do you notice?",
    "axis": "What do the QRS complexes in the limb leads suggest about the overall electrical axis?",
    "p_waves": "Can you identify consistent P waves before each QRS complex?",
    "pr_interval": "Compare the PR interval across several beats. Does it appear consistent?",
    "qrs": "Are the QRS complexes narrow or wide? What measurement or visual feature supports your answer?",
    "st_t": "Look at the ST segment relative to the baseline. What do you observe?",
    "interpretation": "Which of your individual findings most strongly supports your overall interpretation?",
    "overall_reasoning": "How does each observation connect to the interpretation you gave?",
}

_HINTS = {
    "rate": (
        "Consider the spacing between QRS complexes and the ECG recording speed.",
        "Use a consistent method, such as counting large squares between consecutive QRS complexes or counting beats over a known interval.",
    ),
    "rhythm": (
        "Look specifically at the distance between consecutive QRS complexes.",
        "Compare several consecutive R–R intervals rather than judging from a single pair of beats.",
    ),
    "axis": (
        "Consider the direction of the QRS complexes in leads I and aVF.",
        "Compare whether the QRS complexes are predominantly positive or negative in the limb leads.",
    ),
    "p_waves": (
        "Inspect the baseline before each QRS complex in several leads.",
        "Compare the timing and shape of possible P waves across beats, and note whether each relates consistently to a QRS.",
    ),
    "pr_interval": (
        "Focus on the time from the start of a P wave to the start of the following QRS.",
        "Compare that interval across beats and consider its measured duration against standard ECG intervals.",
    ),
    "qrs": (
        "Focus on the width of each QRS complex on the ECG grid.",
        "Estimate the duration from the beginning to the end of the QRS and compare it with the usual narrow-complex range.",
    ),
    "st_t": (
        "First identify the isoelectric baseline, then compare the ST segment and T waves with it.",
        "Review the ST segment and T-wave shape across leads, describing the pattern and location without jumping to a conclusion.",
    ),
    "interpretation": (
        "Separate what you observed from what you think those observations mean.",
        "Review whether the interpretation accounts for the rate, rhythm, intervals, QRS, and ST/T observations you recorded.",
    ),
    "overall_reasoning": (
        "Choose the specific observations that most influenced your interpretation.",
        "Link each important observation to the part of your interpretation it supports, and note any uncertainty.",
    ),
}

_EXPLANATIONS = {
    "missing_reasoning": "A clear explanation connects an answer to an observable ECG feature, making the reasoning easier to review and improve.",
    "weak_reasoning": "Useful ECG reasoning names the feature observed and explains how it supports the response, rather than relying on a guess.",
    "reasoning_contradiction": "A rhythm description and the evidence cited for it should be considered together; interval variability is relevant when describing rhythm regularity.",
    "missing_answer": "Recording the observation before interpreting it helps keep evidence distinct from the conclusion.",
    "incorrect_answer": "Revisit the underlying observation and compare it with the relevant ECG feature before revising your conclusion.",
    "partial_answer": "A more complete response describes the relevant feature and its relationship to nearby ECG components or other leads.",
    "unsupported_conclusion": "An interpretation is stronger when it is explicitly linked to the observations that support it.",
    "not_evaluated": "This case does not yet have enough validated reference information for correctness feedback. Focus on explaining the evidence you used.",
}

_PRIORITY = {
    "reasoning_contradiction": 0,
    "missing_observation": 1,
    "missing_answer": 1,
    "missing_reasoning": 1,
    "unsupported_conclusion": 2,
    "incorrect_answer": 3,
    "partial_answer": 3,
    "weak_reasoning": 4,
    "not_evaluated": 5,
}

_ACTIONS = {
    "reasoning_contradiction": NextAction.RECHECK_RR_INTERVALS.value,
    "missing_reasoning": NextAction.ADD_REASONING.value,
    "weak_reasoning": NextAction.EXPLAIN_EVIDENCE.value,
    "missing_answer": NextAction.REVIEW_OBSERVATION.value,
    "missing_observation": NextAction.REVIEW_OBSERVATION.value,
    "unsupported_conclusion": NextAction.EXPLAIN_EVIDENCE.value,
    "incorrect_answer": NextAction.REVIEW_OBSERVATION.value,
    "partial_answer": NextAction.REVIEW_OBSERVATION.value,
    "not_evaluated": NextAction.REFLECT_ON_FINDINGS.value,
}


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def _mapping(value: Any) -> Mapping[str, Any]:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    elif hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    return value if isinstance(value, Mapping) else {}


def _items(value: Any) -> list[Any]:
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def _issue_feedback(step: str, issue_type: str, severity: FeedbackSeverity) -> FeedbackItem:
    question = _QUESTIONS.get(step, _QUESTIONS["overall_reasoning"])
    if issue_type == "not_evaluated":
        question = _EXPLANATIONS["not_evaluated"]
    return FeedbackItem(
        step=step,
        severity=severity,
        issue_type=issue_type,
        message=question,
        hint_level=int(HintLevel.GUIDING_QUESTION),
        next_action=_ACTIONS.get(issue_type, NextAction.REFLECT_ON_FINDINGS.value),
    )


def _collect_candidates(evaluation_result: Any) -> list[tuple[int, FeedbackItem]]:
    evaluation = _mapping(evaluation_result)
    candidates: list[tuple[int, FeedbackItem]] = []
    seen: set[tuple[str, str]] = set()

    for contradiction in _items(evaluation.get("contradictions")):
        issue = _mapping(contradiction)
        issue_type = str(issue.get("type", "reasoning_contradiction"))
        steps = _items(issue.get("steps")) or ["rhythm"]
        for step in steps:
            item = _issue_feedback(str(step), issue_type, FeedbackSeverity.ATTENTION)
            key = (item.step, item.issue_type)
            if key not in seen:
                candidates.append((_PRIORITY.get(issue_type, 99), item))
                seen.add(key)

    for issue in _items(evaluation.get("reasoning_issues")):
        issue_data = _mapping(issue)
        issue_type = str(issue_data.get("type", "weak_reasoning"))
        steps = _items(issue_data.get("steps")) or ["overall_reasoning"]
        for step in steps:
            item = _issue_feedback(
                str(step),
                issue_type,
                FeedbackSeverity.ATTENTION if issue_type in {"missing_reasoning", "unsupported_conclusion"} else FeedbackSeverity.SUGGESTION,
            )
            key = (item.step, item.issue_type)
            if key not in seen:
                candidates.append((_PRIORITY.get(issue_type, 99), item))
                seen.add(key)

    has_not_evaluated_step = False
    for step_result in _items(evaluation.get("step_results")):
        result = _mapping(step_result)
        step = str(result.get("step", "overall_reasoning"))
        status = str(_value(result.get("status", "")))
        quality = str(_value(result.get("reasoning_quality", "")))
        issues = _items(result.get("issues"))
        if status == "not_evaluated":
            has_not_evaluated_step = True
            continue
        elif status == "missing":
            issue_type = "missing_answer"
        elif status == "incorrect":
            issue_type = "incorrect_answer"
        elif status == "partially_correct":
            issue_type = "partial_answer"
        elif any(str(_mapping(issue).get("type", "")) == "missing_reasoning" for issue in issues):
            issue_type = "missing_reasoning"
        elif quality == "weak":
            issue_type = "weak_reasoning"
        else:
            continue

        item = _issue_feedback(
            step,
            issue_type,
            FeedbackSeverity.INFORMATION if issue_type == "not_evaluated" else FeedbackSeverity.SUGGESTION,
        )
        key = (item.step, item.issue_type)
        if key not in seen:
            candidates.append((_PRIORITY.get(issue_type, 99), item))
            seen.add(key)

    if has_not_evaluated_step and ("overall_reasoning", "not_evaluated") not in seen:
        item = _issue_feedback("overall_reasoning", "not_evaluated", FeedbackSeverity.INFORMATION)
        candidates.append((_PRIORITY["not_evaluated"], item))

    if not candidates and str(_value(evaluation.get("overall_status", ""))) == "not_evaluated":
        item = _issue_feedback("overall_reasoning", "not_evaluated", FeedbackSeverity.INFORMATION)
        candidates.append((_PRIORITY["not_evaluated"], item))
    return candidates


def generate_feedback(evaluation_result: Any) -> list[FeedbackItem]:
    """Create a short prioritized list of learner-facing guiding questions."""
    candidates = _collect_candidates(evaluation_result)
    candidates.sort(key=lambda pair: pair[0])
    return [item for _, item in candidates[:MAX_FEEDBACK_ITEMS]]


def get_hint(
    evaluation_result: Any,
    step: str,
    hint_level: int,
    issue_type: str | None = None,
) -> FeedbackItem:
    """Return one hint level for a step, capped at the full explanation."""
    candidates = [
        item
        for _, item in _collect_candidates(evaluation_result)
        if item.step == step and (issue_type is None or item.issue_type == issue_type)
    ]
    if candidates:
        base = candidates[0]
    else:
        base = _issue_feedback(step, issue_type or "weak_reasoning", FeedbackSeverity.SUGGESTION)

    safe_level = min(max(int(hint_level), int(HintLevel.GUIDING_QUESTION)), MAX_HINT_LEVEL)
    if base.issue_type == "not_evaluated":
        message = _EXPLANATIONS["not_evaluated"]
    elif safe_level == HintLevel.GUIDING_QUESTION:
        message = _QUESTIONS.get(step, _QUESTIONS["overall_reasoning"])
    elif safe_level == HintLevel.SPECIFIC_HINT:
        message = _HINTS.get(step, _HINTS["overall_reasoning"])[1]
    else:
        message = _EXPLANATIONS.get(base.issue_type, _EXPLANATIONS["weak_reasoning"])
    return FeedbackItem(
        step=base.step,
        severity=base.severity,
        issue_type=base.issue_type,
        message=message,
        hint_level=safe_level,
        next_action=base.next_action,
    )
