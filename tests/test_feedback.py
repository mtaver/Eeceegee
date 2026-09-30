"""Tests for the Streamlit-independent Socratic feedback engine."""

from services.evaluator import (
    EvaluationIssue,
    EvaluationResult,
    EvaluationStatus,
    ReasoningQuality,
    StepEvaluation,
)
from services.feedback import (
    HintLevel,
    generate_feedback,
    get_hint,
)


def _evaluation(*, status=EvaluationStatus.NOT_EVALUATED, issues=None, contradictions=None):
    return EvaluationResult(
        case_id="case_test",
        overall_status=status,
        step_results=[
            StepEvaluation(
                step="rhythm",
                status=status,
                reasoning_quality=ReasoningQuality.MISSING if issues else ReasoningQuality.NOT_EVALUATED,
                issues=issues or [],
            )
        ],
        reasoning_issues=issues or [],
        strengths=[],
        missing_elements=[],
        contradictions=contradictions or [],
        confidence=3,
    )


def test_feedback_is_generated_from_evaluation_result():
    feedback = generate_feedback(_evaluation())
    assert feedback
    assert feedback[0].step == "rhythm"
    assert feedback[0].hint_level == HintLevel.GUIDING_QUESTION


def test_missing_reasoning_produces_useful_feedback():
    issue = EvaluationIssue(
        type="missing_reasoning",
        message="The learner provided an answer without reasoning.",
        steps=["rhythm"],
    )
    feedback = generate_feedback(_evaluation(issues=[issue]))
    assert feedback[0].issue_type == "missing_reasoning"
    assert "R–R intervals" in feedback[0].message


def test_contradiction_produces_a_guiding_question():
    contradiction = EvaluationIssue(
        type="reasoning_contradiction",
        message="A possible rhythm contradiction.",
        steps=["rhythm"],
    )
    feedback = generate_feedback(_evaluation(contradictions=[contradiction]))
    assert feedback[0].issue_type == "reasoning_contradiction"
    assert "Compare" in feedback[0].message
    assert feedback[0].hint_level == 1


def test_hint_level_one_is_a_guiding_question():
    hint = get_hint(_evaluation(), "rhythm", 1)
    assert hint.hint_level == 1
    assert "What pattern" in hint.message


def test_hint_level_two_is_a_more_specific_hint():
    hint = get_hint(_evaluation(), "rhythm", 2)
    assert hint.hint_level == 2
    assert "consecutive R–R" in hint.message


def test_hint_level_three_is_an_explanation():
    contradiction = EvaluationIssue(
        type="reasoning_contradiction",
        message="A possible rhythm contradiction.",
        steps=["rhythm"],
    )
    hint = get_hint(_evaluation(contradictions=[contradiction]), "rhythm", 3)
    assert hint.hint_level == 3
    assert "interval variability" in hint.message


def test_hint_progression_is_capped_at_level_three():
    hint = get_hint(_evaluation(), "rhythm", 9)
    assert hint.hint_level == 3
    assert hint.message == get_hint(_evaluation(), "rhythm", 3).message


def test_not_evaluated_returns_safe_nonjudgmental_feedback():
    feedback = generate_feedback(_evaluation())
    assert "not yet have enough validated reference information" in feedback[0].message
    assert "wrong" not in feedback[0].message.lower()


def test_feedback_does_not_expose_hidden_reference_data():
    evaluation = _evaluation()
    evaluation.reasoning_issues.append(
        EvaluationIssue(
            type="not_evaluated",
            message="private reference answer",
            steps=["rhythm"],
        )
    )
    feedback_text = repr([item.to_dict() for item in generate_feedback(evaluation)])
    assert "private reference answer" not in feedback_text


def test_feedback_prioritizes_contradiction_and_limits_items():
    issues = [
        EvaluationIssue(type="weak_reasoning", message="weak", steps=["rate"]),
        EvaluationIssue(type="missing_reasoning", message="missing", steps=["axis"]),
        EvaluationIssue(type="unsupported_conclusion", message="unsupported", steps=["interpretation"]),
    ]
    contradiction = EvaluationIssue(
        type="reasoning_contradiction",
        message="conflict",
        steps=["rhythm"],
    )
    feedback = generate_feedback(_evaluation(issues=issues, contradictions=[contradiction]))
    assert len(feedback) <= 3
    assert feedback[0].issue_type == "reasoning_contradiction"
    assert [item.issue_type for item in feedback][1] == "missing_reasoning"
