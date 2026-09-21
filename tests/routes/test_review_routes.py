"""Route tests for review choices."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.auth_manager import auth_manager
from app.services.learning.review_service import ReviewOutcome


def _set_authenticated_user(monkeypatch, spreadsheet_id: str = "sheet-123") -> None:
    monkeypatch.setattr(auth_manager, "is_authenticated", lambda: True)
    monkeypatch.setattr(
        type(auth_manager),
        "user",
        property(lambda self: SimpleNamespace(get_active_spreadsheet_id=lambda: spreadsheet_id)),
    )


@pytest.mark.parametrize(
    ("outcome", "expected_outcome"),
    [
        ("forgotten", ReviewOutcome.FORGOTTEN),
        ("remembered", ReviewOutcome.REMEMBERED),
    ],
)
def test_review_answer_records_choice_and_advances(client, monkeypatch, outcome, expected_outcome):
    """Both review buttons map to the correct service choice."""
    _set_authenticated_user(monkeypatch)
    calls = []

    class FakeReviewService:
        def record_review(self, outcome: ReviewOutcome, spreadsheet_id: str):
            calls.append((outcome, spreadsheet_id))
            return SimpleNamespace(success=True, completed=False, error=None)

    monkeypatch.setattr("app.routes.review.ReviewService", FakeReviewService)

    response = client.post(f"/review/answer/{outcome}")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/review/card")
    assert calls == [(expected_outcome, "sheet-123")]


def test_review_answer_returns_home_after_last_card(client, monkeypatch):
    """Completing the review stack returns to the dashboard."""
    _set_authenticated_user(monkeypatch)

    class FakeReviewService:
        def record_review(self, outcome: ReviewOutcome, spreadsheet_id: str):
            return SimpleNamespace(success=True, completed=True, error=None)

    monkeypatch.setattr("app.routes.review.ReviewService", FakeReviewService)

    response = client.post("/review/answer/remembered")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_review_answer_keeps_back_visible_when_save_fails(client, monkeypatch):
    """A failed write stays on the same card and surfaces a retryable error."""
    _set_authenticated_user(monkeypatch)

    class FakeReviewService:
        def record_review(self, outcome: ReviewOutcome, spreadsheet_id: str):
            return SimpleNamespace(success=False, completed=False, error="failed")

    monkeypatch.setattr("app.routes.review.ReviewService", FakeReviewService)

    response = client.post("/review/answer/forgotten")

    assert response.status_code == 302
    assert "/review/flip?error=" in response.headers["Location"]


def test_review_answer_rejects_unknown_outcome(client, monkeypatch):
    """Only the two explicit review outcomes are accepted."""
    _set_authenticated_user(monkeypatch)

    response = client.post("/review/answer/skipped")

    assert response.status_code == 400


def test_end_review_early_is_post_only(client, monkeypatch):
    """Early review completion cannot be triggered by a link prefetch or crawler."""
    _set_authenticated_user(monkeypatch)

    response = client.get("/review/end")

    assert response.status_code == 405


def test_end_review_early_saves_progress_and_returns_home(client, monkeypatch):
    """The early-end route delegates persistence before returning home."""
    _set_authenticated_user(monkeypatch)
    calls = []

    class FakeReviewService:
        def end_session_early(self, spreadsheet_id: str):
            calls.append(spreadsheet_id)
            return SimpleNamespace(success=True, completed=True, error=None)

    monkeypatch.setattr("app.routes.review.ReviewService", FakeReviewService)

    response = client.post("/review/end")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    assert calls == ["sheet-123"]


def test_end_review_early_save_failure_returns_to_current_card(client, monkeypatch):
    """A failed early-end write redirects to the active card with an error."""
    _set_authenticated_user(monkeypatch)

    class FakeReviewService:
        def end_session_early(self, spreadsheet_id: str):
            return SimpleNamespace(success=False, completed=False, error="failed")

    monkeypatch.setattr("app.routes.review.ReviewService", FakeReviewService)

    response = client.post("/review/end")

    assert response.status_code == 302
    assert "/review/card?error=" in response.headers["Location"]
