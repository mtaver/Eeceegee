"""Tests for deterministic, reference-aware reasoning evaluation."""

from services.evaluator import (
    EvaluationStatus,
    ReasoningQuality,
    evaluate_attempt,
    evaluate_interpretation,
    evaluate_rate,
    evaluate_rhythm,
)
from services.reasoning import FINDING_FIELDS, create_reasoning_attempt


def _empty_reference_case():
    return {
        "id": "case_test",
        "reference_findings": {field: "" for field in FINDING_FIELDS},
        "reference_interpretation": "",
    }


def _complete_attempt():
    attempt = create_reasoning_attempt("case_test")
    for field in FINDING_FIELDS:
        attempt[field] = {
            "answer": f"learner observation for {field}",
            "reasoning": f"I reviewed the ECG feature for {field}.",
        }
    attempt["interpretation"] = "Learner's own interpretation"
    attempt["overall_reasoning"] = "These observations informed my interpretation."
    attempt["confidence"] = 4
    return attempt


def test_empty_reference_data_returns_not_evaluated():
    result = evaluate_rate(
        {"answer": "72", "reasoning": "Counted the complexes over time."},
        _empty_reference_case(),
    )
    assert result.status == EvaluationStatus.NOT_EVALUATED


def test_missing_learner_answer_returns_missing():
    result = evaluate_rate({"answer": "", "reasoning": ""}, _empty_reference_case())
    assert result.status == EvaluationStatus.MISSING


def test_answer_without_reasoning_produces_missing_reasoning_issue():
    result = evaluate_rhythm({"answer": "Regular", "reasoning": ""}, _empty_reference_case())
    assert any(issue.type == "missing_reasoning" for issue in result.issues)
    assert result.reasoning_quality == ReasoningQuality.MISSING


def test_answer_with_reasoning_is_recognized():
    result = evaluate_rhythm(
        {"answer": "Regular", "reasoning": "The R-R intervals are evenly spaced."},
        _empty_reference_case(),
    )
    assert result.reasoning_quality == ReasoningQuality.ADEQUATE
    assert result.strengths


def test_weak_reasoning_is_flagged():
    result = evaluate_rhythm({"answer": "Regular", "reasoning": "I think so."}, _empty_reference_case())
    assert result.reasoning_quality == ReasoningQuality.WEAK


def test_confidence_is_preserved():
    result = evaluate_attempt(_empty_reference_case(), _complete_attempt())
    assert result.confidence == 4


def test_simple_rhythm_contradiction_is_detected():
    attempt = _complete_attempt()
    attempt["rhythm"] = {
        "answer": "Regular",
        "reasoning": "The R-R intervals vary considerably across the tracing.",
    }
    result = evaluate_attempt(_empty_reference_case(), attempt)
    assert len(result.contradictions) == 1
    assert result.contradictions[0].type == "reasoning_contradiction"
    assert result.contradictions[0].steps == ["rhythm"]


def test_evaluate_attempt_returns_expected_structure():
    result = evaluate_attempt(_empty_reference_case(), _complete_attempt())
    output = result.to_dict()
    assert output["case_id"] == "case_test"
    assert output["overall_status"] == EvaluationStatus.NOT_EVALUATED
    assert len(output["step_results"]) == len(FINDING_FIELDS) + 1
    assert {step["step"] for step in output["step_results"]} == {*FINDING_FIELDS, "interpretation"}
    assert {"reasoning_issues", "strengths", "missing_elements", "contradictions", "confidence"}.issubset(output)


def test_evaluation_result_does_not_expose_reference_data():
    case = _empty_reference_case()
    case["reference_findings"] = {"rate": "72 bpm", "secret": "private reference"}
    case["reference_interpretation"] = "private interpretation"
    output = evaluate_attempt(case, _complete_attempt()).to_dict()
    assert "reference_findings" not in output
    assert "reference_interpretation" not in output
    assert "private reference" not in repr(output)
    assert "private interpretation" not in repr(output)


def test_malformed_or_incomplete_attempt_is_handled_gracefully():
    result = evaluate_attempt(None, {"rhythm": "not-a-dict", "confidence": "high"})
    assert result.case_id is None
    assert result.confidence is None
    assert all(step.status == EvaluationStatus.MISSING for step in result.step_results)


def test_missing_interpretation_is_missing_even_without_reference():
    result = evaluate_interpretation("", _empty_reference_case())
    assert result.status == EvaluationStatus.MISSING


def test_unanswered_interpretation_with_no_reference_is_not_scored():
    result = evaluate_interpretation("Learner's interpretation", _empty_reference_case())
    assert result.status == EvaluationStatus.NOT_EVALUATED
