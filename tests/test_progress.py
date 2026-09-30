"""Tests for pure learner progress and attempt tracking services."""

from services.progress import (
    PROGRESS_STEPS,
    create_progress,
    get_progress_summary,
    get_recent_attempts,
    get_step_statistics,
    record_attempt,
    record_case_started,
    record_hint_usage,
    record_revision,
)


def _attempt(confidence=4):
    return {
        "case_id": "case_001",
        **{
            step: {"answer": f"answer {step}", "reasoning": f"evidence for {step}"}
            for step in PROGRESS_STEPS[:-1]
        },
        "interpretation": "learner interpretation",
        "overall_reasoning": "observations support my conclusion",
        "confidence": confidence,
    }


def _evaluation(*, rhythm_quality="adequate", rhythm_issues=None):
    results = []
    for step in PROGRESS_STEPS:
        quality = rhythm_quality if step == "rhythm" else "adequate"
        results.append(
            {
                "step": step,
                "status": "not_evaluated",
                "reasoning_quality": quality,
                "issues": rhythm_issues if step == "rhythm" else [],
            }
        )
    return {
        "case_id": "case_001",
        "overall_status": "not_evaluated",
        "step_results": results,
        "reasoning_issues": [],
        "contradictions": [],
        "confidence": 4,
    }


def test_new_progress_starts_empty():
    progress = create_progress()
    assert progress["total_attempts"] == 0
    assert progress["total_cases_started"] == 0
    assert progress["total_cases_completed"] == 0
    assert progress["total_revisions"] == 0
    assert progress["average_confidence"] is None
    assert set(progress["step_statistics"]) == set(PROGRESS_STEPS)


def test_recording_attempt_updates_totals_and_completion():
    progress = create_progress()
    history = []
    record_case_started(progress, "case_001")
    record_attempt(
        progress,
        _attempt(),
        _evaluation(),
        timestamp="2026-01-01T00:00:00+00:00",
        attempt_history=history,
    )
    assert progress["total_attempts"] == 1
    assert progress["total_cases_completed"] == 1
    assert len(history) == 1
    assert history[0]["attempt_number"] == 1


def test_case_start_count_is_unique():
    progress = create_progress()
    record_case_started(progress, "case_001")
    record_case_started(progress, "case_001")
    assert progress["total_cases_started"] == 1


def test_revision_count_increases_correctly():
    progress = create_progress()
    history = []
    record = record_attempt(
        progress,
        _attempt(),
        _evaluation(),
        timestamp="2026-01-01T00:00:00+00:00",
        attempt_history=history,
    )
    record_revision(progress, record)
    record_revision(progress, record)
    assert progress["total_revisions"] == 1
    assert record["revised"] is True


def test_confidence_aggregation_works():
    progress = create_progress()
    history = []
    for confidence, stamp in ((3, "2026-01-01T00:00:00+00:00"), (5, "2026-01-02T00:00:00+00:00")):
        record_attempt(
            progress,
            _attempt(confidence),
            _evaluation(),
            timestamp=stamp,
            attempt_history=history,
        )
    assert progress["average_confidence"] == 4.0


def test_step_statistics_update_correctly():
    progress = create_progress()
    history = []
    evaluation = _evaluation(
        rhythm_quality="contradictory",
        rhythm_issues=[{"type": "reasoning_contradiction"}],
    )
    record_attempt(progress, _attempt(), evaluation, attempt_history=history)
    stats = get_step_statistics(progress)["rhythm"]
    assert stats["attempts"] == 1
    assert stats["issues"] >= 1
    assert stats["weak_reasoning"] == 1
    assert stats["recurring_problems"]["reasoning_contradiction"] == 1


def test_strengths_derive_from_repeated_evidence():
    progress = create_progress()
    history = []
    for day in (1, 2):
        record_attempt(
            progress,
            _attempt(),
            _evaluation(),
            timestamp=f"2026-01-0{day}T00:00:00+00:00",
            attempt_history=history,
        )
    assert "Rate reasoning" in progress["reasoning_strengths"]


def test_weaknesses_derive_from_repeated_issues():
    progress = create_progress()
    history = []
    evaluation = _evaluation(
        rhythm_quality="contradictory",
        rhythm_issues=[{"type": "reasoning_contradiction"}],
    )
    for day in (1, 2):
        record_attempt(
            progress,
            _attempt(),
            evaluation,
            timestamp=f"2026-01-0{day}T00:00:00+00:00",
            attempt_history=history,
        )
    assert "Rhythm reasoning" in progress["reasoning_weaknesses"]


def test_resolved_issue_is_detected_after_revision():
    progress = create_progress()
    history = []
    with_issue = _evaluation(
        rhythm_quality="contradictory",
        rhythm_issues=[{"type": "reasoning_contradiction"}],
    )
    first = record_attempt(
        progress,
        _attempt(),
        with_issue,
        timestamp="2026-01-01T00:00:00+00:00",
        attempt_history=history,
    )
    record_revision(progress, first)
    revised = record_attempt(
        progress,
        _attempt(),
        _evaluation(),
        timestamp="2026-01-02T00:00:00+00:00",
        attempt_history=history,
    )
    assert revised["resolved_issues"]["rhythm"] == ["reasoning_contradiction"]
    assert progress["feedback_issues_addressed"] == 1
    assert get_progress_summary(progress)["recent_improvements"]


def test_feedback_hint_usage_is_tracked():
    progress = create_progress()
    history = []
    record = record_attempt(progress, _attempt(), _evaluation(), attempt_history=history)
    record_hint_usage(progress, record, "rhythm", 2)
    assert progress["hints_requested"] == 1
    assert get_progress_summary(progress)["average_hint_level"] == 2
    assert history[0]["hints_requested"] == 1


def test_summary_has_expected_structure_and_no_reference_data():
    progress = create_progress()
    history = []
    record_attempt(progress, _attempt(), _evaluation(), attempt_history=history)
    summary = get_progress_summary(progress)
    assert {
        "cases_started",
        "cases_completed",
        "attempts",
        "revisions",
        "average_confidence",
        "top_strengths",
        "areas_for_practice",
        "recent_improvements",
        "step_statistics",
    }.issubset(summary)
    assert "reference_findings" not in repr(summary)
    assert "reference_interpretation" not in repr(summary)


def test_empty_progress_and_recent_attempts_are_safe():
    summary = get_progress_summary(None)
    assert summary["attempts"] == 0
    assert summary["recent_attempts"] == []
    assert get_recent_attempts(create_progress()) == []


def test_confidence_and_reasoning_pattern_uses_neutral_wording():
    progress = create_progress()
    quality = _evaluation(rhythm_quality="weak")
    record_attempt(progress, _attempt(confidence=5), quality)
    summary = get_progress_summary(progress)
    assert "Confidence was high while reasoning evidence was limited." in summary["confidence_reasoning_patterns"]
