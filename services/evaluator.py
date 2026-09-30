"""Deterministic, reference-aware evaluation of learner ECG reasoning."""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping

from services.reasoning import FINDING_FIELDS


class EvaluationStatus(str, Enum):
    CORRECT = "correct"
    PARTIALLY_CORRECT = "partially_correct"
    INCORRECT = "incorrect"
    MISSING = "missing"
    UNABLE_TO_DETERMINE = "unable_to_determine"
    NOT_EVALUATED = "not_evaluated"


class ReasoningQuality(str, Enum):
    STRONG = "strong"
    ADEQUATE = "adequate"
    WEAK = "weak"
    CONTRADICTORY = "contradictory"
    MISSING = "missing"
    NOT_EVALUATED = "not_evaluated"


@dataclass
class EvaluationIssue:
    type: str
    message: str
    steps: list[str] = field(default_factory=list)


@dataclass
class StepEvaluation:
    step: str
    status: EvaluationStatus
    reasoning_quality: ReasoningQuality
    issues: list[EvaluationIssue] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    feedback_needed: bool = False


@dataclass
class EvaluationResult:
    case_id: str | None
    overall_status: EvaluationStatus
    step_results: list[StepEvaluation]
    reasoning_issues: list[EvaluationIssue]
    strengths: list[str]
    missing_elements: list[str]
    contradictions: list[EvaluationIssue]
    confidence: int | None

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable result containing no reference-case fields."""
        return asdict(self)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _reference_value(reference: Any, step: str) -> Any:
    findings = _as_mapping(_as_mapping(reference).get("reference_findings"))
    if step == "interpretation":
        return _as_mapping(reference).get("reference_interpretation")
    return findings.get(step)


def _has_reference(reference_value: Any) -> bool:
    if reference_value is None:
        return False
    if isinstance(reference_value, str):
        return bool(reference_value.strip())
    if isinstance(reference_value, Mapping):
        return any(_has_reference(value) for value in reference_value.values())
    if isinstance(reference_value, (list, tuple, set)):
        return any(_has_reference(value) for value in reference_value)
    return bool(reference_value)


def _matches_reference(answer: str, reference_value: Any) -> bool | None:
    """Compare simple textual references; return None for unsupported shapes."""
    if isinstance(reference_value, str):
        return answer.casefold() == reference_value.strip().casefold()
    if isinstance(reference_value, (int, float)) and not isinstance(reference_value, bool):
        try:
            return float(answer) == float(reference_value)
        except ValueError:
            return False
    if isinstance(reference_value, (list, tuple, set)):
        return answer.casefold() in {str(value).strip().casefold() for value in reference_value}
    if isinstance(reference_value, Mapping):
        expected = reference_value.get("answer")
        return _matches_reference(answer, expected) if _has_reference(expected) else None
    return None


def _reasoning_quality(answer: str, reasoning: str) -> tuple[ReasoningQuality, list[EvaluationIssue]]:
    if not answer:
        return ReasoningQuality.MISSING, []
    if not reasoning:
        return ReasoningQuality.MISSING, [
            EvaluationIssue(
                type="missing_reasoning",
                message="You provided an answer but did not explain the observation supporting it.",
            )
        ]
    normalized = reasoning.casefold().strip(" .,!?")
    weak_phrases = {"i think so", "i think", "because", "not sure", "guess", "just because"}
    if normalized in weak_phrases or len(normalized.split()) < 3:
        return ReasoningQuality.WEAK, [
            EvaluationIssue(
                type="weak_reasoning",
                message="Consider describing the specific ECG feature that supports your answer.",
            )
        ]
    return ReasoningQuality.ADEQUATE, []


def _evaluate_step(step: str, learner_response: Any, reference: Any) -> StepEvaluation:
    response = _as_mapping(learner_response)
    answer = _text(response.get("answer"))
    reasoning = _text(response.get("reasoning"))
    quality, issues = _reasoning_quality(answer, reasoning)
    reference_value = _reference_value(reference, step)

    if not answer:
        status = EvaluationStatus.MISSING
    elif answer.casefold() in {"unable to determine", "unable to assess", "cannot determine"}:
        status = EvaluationStatus.UNABLE_TO_DETERMINE
    elif not _has_reference(reference_value):
        status = EvaluationStatus.NOT_EVALUATED
    else:
        match = _matches_reference(answer, reference_value)
        status = (
            EvaluationStatus.NOT_EVALUATED
            if match is None
            else EvaluationStatus.CORRECT
            if match
            else EvaluationStatus.INCORRECT
        )

    strengths = ["You provided an explanation for this finding."] if reasoning and quality == ReasoningQuality.ADEQUATE else []
    return StepEvaluation(
        step=step,
        status=status,
        reasoning_quality=quality,
        issues=issues,
        strengths=strengths,
        feedback_needed=bool(issues) or status in {EvaluationStatus.MISSING, EvaluationStatus.INCORRECT},
    )


def evaluate_rate(response: Any, reference: Any) -> StepEvaluation:
    return _evaluate_step("rate", response, reference)


def evaluate_rhythm(response: Any, reference: Any) -> StepEvaluation:
    return _evaluate_step("rhythm", response, reference)


def evaluate_axis(response: Any, reference: Any) -> StepEvaluation:
    return _evaluate_step("axis", response, reference)


def evaluate_p_waves(response: Any, reference: Any) -> StepEvaluation:
    return _evaluate_step("p_waves", response, reference)


def evaluate_pr_interval(response: Any, reference: Any) -> StepEvaluation:
    return _evaluate_step("pr_interval", response, reference)


def evaluate_qrs(response: Any, reference: Any) -> StepEvaluation:
    return _evaluate_step("qrs", response, reference)


def evaluate_st_t(response: Any, reference: Any) -> StepEvaluation:
    return _evaluate_step("st_t", response, reference)


def evaluate_interpretation(answer: Any, reference: Any) -> StepEvaluation:
    response = _text(answer)
    reference_value = _reference_value(reference, "interpretation")
    if not response:
        status = EvaluationStatus.MISSING
    elif not _has_reference(reference_value):
        status = EvaluationStatus.NOT_EVALUATED
    else:
        match = _matches_reference(response, reference_value)
        status = (
            EvaluationStatus.NOT_EVALUATED
            if match is None
            else EvaluationStatus.CORRECT
            if match
            else EvaluationStatus.INCORRECT
        )
    return StepEvaluation(
        step="interpretation",
        status=status,
        reasoning_quality=ReasoningQuality.NOT_EVALUATED,
        issues=[],
        feedback_needed=status in {EvaluationStatus.MISSING, EvaluationStatus.INCORRECT},
    )


_EVALUATORS = {
    "rate": evaluate_rate,
    "rhythm": evaluate_rhythm,
    "axis": evaluate_axis,
    "p_waves": evaluate_p_waves,
    "pr_interval": evaluate_pr_interval,
    "qrs": evaluate_qrs,
    "st_t": evaluate_st_t,
}


def _find_contradictions(attempt: Mapping[str, Any]) -> list[EvaluationIssue]:
    """Detect a narrow, explicit regular-rhythm vs varying-RR contradiction."""
    rhythm = _as_mapping(attempt.get("rhythm"))
    answer = _text(rhythm.get("answer")).casefold()
    reasoning = _text(rhythm.get("reasoning")).casefold()
    if answer == "regular" and any(
        phrase in reasoning
        for phrase in ("rr intervals vary", "r-r intervals vary", "varying r-r", "varying rr", "intervals are irregular")
    ):
        return [
            EvaluationIssue(
                type="reasoning_contradiction",
                steps=["rhythm"],
                message="You described the rhythm as regular, while your reasoning describes variability in the R-R intervals. Please review how these observations fit together.",
            )
        ]
    return []


def evaluate_attempt(case: Any, attempt: Any) -> EvaluationResult:
    """Evaluate a learner attempt using only available case reference data."""
    case_data = _as_mapping(case)
    learner = _as_mapping(attempt)
    if not case_data:
        case_data = {
            "id": None,
            "reference_findings": {},
            "reference_interpretation": "",
        }
    step_results = [
        evaluator(learner.get(step), case_data)
        for step, evaluator in _EVALUATORS.items()
    ]
    step_results.append(evaluate_interpretation(learner.get("interpretation"), case_data))

    contradictions = _find_contradictions(learner)
    for contradiction in contradictions:
        for result in step_results:
            if result.step in contradiction.steps:
                result.reasoning_quality = ReasoningQuality.CONTRADICTORY
                result.issues.append(contradiction)
                result.feedback_needed = True

    overall_reasoning = _text(learner.get("overall_reasoning"))
    if not overall_reasoning:
        reasoning_issues = [
            EvaluationIssue(
                type="missing_reasoning",
                steps=["overall_reasoning"],
                message="You provided findings but did not explain how they informed your overall interpretation.",
            )
        ]
    elif len(overall_reasoning.split()) < 3:
        reasoning_issues = [
            EvaluationIssue(
                type="weak_reasoning",
                steps=["overall_reasoning"],
                message="Consider explaining how specific observations support your interpretation.",
            )
        ]
    else:
        reasoning_issues = []

    all_issues = reasoning_issues + [issue for result in step_results for issue in result.issues]
    strengths = [strength for result in step_results for strength in result.strengths]
    missing_elements = [result.step for result in step_results if result.status == EvaluationStatus.MISSING]
    if not overall_reasoning:
        missing_elements.append("overall_reasoning")

    statuses = [result.status for result in step_results]
    assessed_statuses = [
        status
        for status in statuses
        if status not in {EvaluationStatus.NOT_EVALUATED, EvaluationStatus.UNABLE_TO_DETERMINE}
    ]
    if EvaluationStatus.MISSING in statuses:
        overall_status = EvaluationStatus.MISSING
    elif not assessed_statuses:
        overall_status = EvaluationStatus.NOT_EVALUATED
    elif all(status == EvaluationStatus.CORRECT for status in assessed_statuses):
        overall_status = EvaluationStatus.CORRECT
    elif all(status == EvaluationStatus.INCORRECT for status in assessed_statuses):
        overall_status = EvaluationStatus.INCORRECT
    else:
        overall_status = EvaluationStatus.PARTIALLY_CORRECT
    confidence = learner.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, int) or not 1 <= confidence <= 5:
        confidence = None

    case_id = case_data.get("id") or learner.get("case_id")
    return EvaluationResult(
        case_id=case_id if isinstance(case_id, str) else None,
        overall_status=overall_status,
        step_results=step_results,
        reasoning_issues=all_issues,
        strengths=strengths,
        missing_elements=missing_elements,
        contradictions=contradictions,
        confidence=confidence,
    )


def evaluate_reasoning(*args: Any, **kwargs: Any) -> EvaluationResult:
    """Backward-friendly alias for the overall attempt evaluator."""
    return evaluate_attempt(*args, **kwargs)
