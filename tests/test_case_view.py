"""Learner-facing ECG image resolution and placeholder behavior."""

import pytest

from components import case_view
from services.case_manager import get_case_for_student


class _StreamlitStub:
    def __init__(self):
        self.session_state = {"reasoning_submitted": True}
        self.images = []
        self.infos = []

    def image(self, path, **kwargs):
        self.images.append(path)

    def info(self, message):
        self.infos.append(message)

    def __getattr__(self, _name):
        return lambda *_args, **_kwargs: None


@pytest.fixture
def streamlit_stub(monkeypatch):
    stub = _StreamlitStub()
    monkeypatch.setattr(case_view, "st", stub)
    monkeypatch.setattr(case_view, "render_feedback_and_revision", lambda: None)
    return stub


@pytest.mark.parametrize(
    ("case_id", "expected_path"),
    [
        ("case_001", "assets/ecg/learner/NSR_001_learner.png"),
        ("case_002", "assets/ecg/learner/SB_001_learner.png"),
    ],
)
def test_existing_learner_image_path_is_displayed(case_id, expected_path, streamlit_stub):
    case = get_case_for_student(case_id)
    assert case is not None and case["image_path"] == expected_path

    case_view.render_case(case, {})

    assert len(streamlit_stub.images) == 1
    assert streamlit_stub.images[0].replace("\\", "/").endswith(expected_path)
    assert streamlit_stub.infos == []


def test_missing_learner_image_shows_placeholder(streamlit_stub):
    case = get_case_for_student("case_001")
    assert case is not None
    case["image_path"] = "assets/ecg/learner/not-present_learner.png"

    case_view.render_case(case, {})

    assert streamlit_stub.images == []
    assert len(streamlit_stub.infos) == 1
    assert "No sourced ECG image is available yet" in streamlit_stub.infos[0]


def test_existing_source_image_is_never_used_as_fallback(streamlit_stub):
    case = get_case_for_student("case_001")
    assert case is not None
    case["image_path"] = "assets/ecg/source/NSR_001.png"

    case_view.render_case(case, {})

    assert streamlit_stub.images == []
    assert len(streamlit_stub.infos) == 1


def test_st_case_without_image_keeps_placeholder(streamlit_stub):
    case = get_case_for_student("case_003")
    assert case is not None and case["image_path"] is None

    case_view.render_case(case, {})

    assert streamlit_stub.images == []
    assert len(streamlit_stub.infos) == 1
    assert "No sourced ECG image is available yet" in streamlit_stub.infos[0]
