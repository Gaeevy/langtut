"""Route tests for learn flow behavior partitions."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.auth_manager import auth_manager


def _set_authenticated_user(monkeypatch, spreadsheet_id: str = "sheet-123") -> None:
    """Patch auth manager to emulate an authenticated user."""
    monkeypatch.setattr(auth_manager, "is_authenticated", lambda: True)
    monkeypatch.setattr(
        type(auth_manager),
        "user",
        property(lambda self: SimpleNamespace(get_active_spreadsheet_id=lambda: spreadsheet_id)),
    )


def _patch_learn_service(
    monkeypatch, process_result: SimpleNamespace, context: SimpleNamespace | None
):
    """Patch LearnService constructor with a deterministic fake."""

    class FakeLearnService:
        def process_answer(self, user_answer: str) -> SimpleNamespace:
            return process_result

        def get_current_card_context(self) -> SimpleNamespace | None:
            return context

    monkeypatch.setattr("app.routes.learn.LearnService", FakeLearnService)


@pytest.mark.parametrize("is_correct", [True, False])
def test_answer_ajax_returns_feedback_payload(client, monkeypatch, is_correct: bool):
    """AJAX answer path returns stable JSON contract for both outcomes."""
    _set_authenticated_user(monkeypatch)

    context = SimpleNamespace(
        card={
            "word": "ola",
            "translation": "hello",
            "example": "ola amigo",
            "example_translation": "hello friend",
            "level": SimpleNamespace(value=3),
        },
        mode="type_answer",
        task_index=2,
        task_total=10,
        progress_sections=[{"label": "L1", "fill_pct": 20}],
        sheet_gid=77,
    )
    _patch_learn_service(
        monkeypatch,
        process_result=SimpleNamespace(success=True, is_correct=is_correct, error=None),
        context=context,
    )

    response = client.post("/learn/answer", json={"user_answer": "hello"})
    assert response.status_code == 200

    payload = response.get_json()
    assert set(payload.keys()) == {
        "success",
        "correct",
        "card",
        "question_mode",
        "task_index",
        "task_total",
        "progress_sections",
        "spreadsheet_id",
        "sheet_gid",
    }
    assert payload["success"] is True
    assert payload["correct"] is is_correct
    assert set(payload["card"].keys()) == {
        "word",
        "translation",
        "example",
        "example_translation",
        "level",
    }
    assert payload["card"]["word"] == "ola"
    assert payload["card"]["level"] == 3
    assert payload["question_mode"] == "type_answer"
    assert payload["task_index"] == 2
    assert payload["task_total"] == 10
    assert payload["spreadsheet_id"] == "sheet-123"
    assert payload["sheet_gid"] == 77


@pytest.mark.parametrize(
    ("process_result", "expected_path"),
    [
        (SimpleNamespace(success=False, is_correct=False, error="boom"), "/"),
        (SimpleNamespace(success=True, is_correct=True, error=None), "/learn/feedback/yes"),
        (SimpleNamespace(success=True, is_correct=False, error=None), "/learn/feedback/no"),
    ],
)
def test_answer_form_redirects_by_outcome(client, monkeypatch, process_result, expected_path: str):
    """Form answer path redirects correctly for failure and correctness outcomes."""
    _set_authenticated_user(monkeypatch)
    _patch_learn_service(monkeypatch, process_result=process_result, context=None)

    response = client.post("/learn/answer", data={"user_answer": "guess"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith(expected_path)
