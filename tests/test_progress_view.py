"""Learner-facing progress terminology and dashboard rendering."""

from contextlib import nullcontext

from components import progress_view
from services.progress import create_progress


class _Metric:
    def metric(self, *_args, **_kwargs):
        pass


class _StreamlitStub:
    def __init__(self):
        self.text = []

    def columns(self, count):
        return [_Metric() for _ in range(count)]

    def expander(self, *_args, **_kwargs):
        return nullcontext()

    def __getattr__(self, name):
        if name in {"write", "markdown", "caption", "subheader", "title"}:
            return lambda value, **_kwargs: self.text.append(str(value))
        return lambda *_args, **_kwargs: None


def test_progress_dashboard_uses_standard_ecg_term_capitalization(monkeypatch):
    progress = create_progress()
    progress["reasoning_strengths"] = ["Qrs reasoning", "St T reasoning", "P Waves reasoning", "PR Interval reasoning"]
    progress["reasoning_weaknesses"] = ["Qrs reasoning", "St T reasoning", "P Waves reasoning", "PR Interval reasoning"]
    progress["recent_attempts"] = [
        {
            "case_id": "case_001",
            "timestamp": "2026-10-01T00:00:00+00:00",
            "resolved_issues": {"qrs": ["incorrect"]},
            "confidence": 3,
            "hints_requested": 0,
            "revised": True,
            "attempt_number": 1,
        }
    ]
    stub = _StreamlitStub()
    monkeypatch.setattr(progress_view, "st", stub)

    progress_view.render_progress(progress)

    assert "- QRS reasoning" in stub.text
    assert "- ST/T reasoning" in stub.text
    assert "- P waves reasoning" in stub.text
    assert "- PR interval reasoning" in stub.text
    assert "- You resolved a QRS reasoning issue identified in an earlier attempt." in stub.text
    for label in ("QRS", "ST/T", "P waves", "PR interval"):
        assert any(text.startswith(f"**{label}**") and "attempts:" in text for text in stub.text)
