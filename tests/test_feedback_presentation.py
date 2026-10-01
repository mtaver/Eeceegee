"""Learner-facing display of submitted answers and Socratic feedback."""

from components import reasoning_form


class _StreamlitStub:
    def __init__(self, feedback_item):
        self.events = []
        self.session_state = {
            "reasoning_feedback": [feedback_item],
            "reasoning_evaluation": {},
            "completed_reasoning_attempt": {
                "p_waves": {
                    "answer": "P waves are present.",
                    "reasoning": "I saw a deflection before each QRS.",
                },
            },
        }

    def __getattr__(self, name):
        def record(*args, **_kwargs):
            self.events.append((name, *args))
            return False

        return record


def _feedback_item(hint_level=1):
    return {
        "step": "p_waves",
        "severity": "suggestion",
        "issue_type": "weak_reasoning",
        "message": "Can you identify consistent P waves before each QRS complex?",
        "hint_level": hint_level,
        "next_action": "review_observation",
    }


def test_feedback_section_shows_the_submitted_response_before_guidance(monkeypatch):
    stub = _StreamlitStub(_feedback_item())
    monkeypatch.setattr(reasoning_form, "st", stub)

    reasoning_form.render_feedback_and_revision()

    assert ("subheader", "Feedback") in stub.events
    displayed_text = [str(value) for event in stub.events for value in event[1:]]
    assert "**Your response · P waves**" in displayed_text
    assert "Observation: P waves are present." in displayed_text
    assert "Reasoning: I saw a deflection before each QRS." in displayed_text
    assert "Can you identify consistent P waves before each QRS complex?" in displayed_text

    response_position = next(i for i, event in enumerate(stub.events) if event[:2] == ("markdown", "**Your response · P waves**"))
    feedback_position = next(i for i, event in enumerate(stub.events) if event[:2] == ("info", "Can you identify consistent P waves before each QRS complex?"))
    assert response_position < feedback_position


def test_hint_level_is_labelled_and_explanation_progression_is_preserved(monkeypatch):
    stub = _StreamlitStub(_feedback_item(hint_level=2))
    monkeypatch.setattr(reasoning_form, "st", stub)

    reasoning_form.render_feedback_and_revision()

    assert ("caption", "P waves · Hint") in stub.events
    assert any(event[0] == "button" and event[1] == "Show Explanation" for event in stub.events)
