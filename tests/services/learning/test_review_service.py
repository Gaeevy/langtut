"""Tests for the review stack and its persistence rules."""

from __future__ import annotations

from datetime import datetime

from app.models import CardSet, Levels
from app.services.learning.review_service import ReviewOutcome, ReviewService
from tests.conftest import make_card


def test_start_session_loads_the_full_card_set(request_context, monkeypatch):
    """Review starts with every card, including cards that are not due."""
    cards = [
        make_card(id=1, level=Levels.LEVEL_0),
        make_card(id=2, level=Levels.LEVEL_8),
    ]
    monkeypatch.setattr(
        "app.services.learning.review_service.read_card_set",
        lambda **kwargs: CardSet(name="Words", gid=42, cards=cards),
    )

    service = ReviewService()
    result = service.start_session("Words", "sheet-123")

    assert result.success is True
    assert result.card_count == 2
    assert service.session.get_total_cards() == 2


def test_forgotten_card_loses_one_level_updates_timestamp_and_advances(
    request_context, monkeypatch
):
    """A left/forgotten choice records a one-level decrease before advancing."""
    reviewed_at = datetime(2026, 9, 21, 10, 30)
    service = ReviewService()
    service.session.initialize(
        [make_card(id=1, level=Levels.LEVEL_3), make_card(id=2)],
        "Words",
        42,
    )
    save_calls = []
    monkeypatch.setattr("app.services.learning.review_service.get_timestamp", lambda: reviewed_at)
    monkeypatch.setattr(
        "app.services.learning.review_service.update_spreadsheet",
        lambda tab, cards, spreadsheet_id: save_calls.append(cards),
    )

    result = service.record_review(ReviewOutcome.FORGOTTEN, spreadsheet_id="sheet-123")

    assert result.success is True
    assert result.completed is False
    assert save_calls == []
    state = service.session.get_state()
    assert state.current_index == 1
    reviewed_card = service.session.deserialize_card(state.cards[0])
    assert reviewed_card.level == Levels.LEVEL_2
    assert reviewed_card.last_shown == reviewed_at


def test_remembered_card_preserves_level_and_only_updates_timestamp(request_context, monkeypatch):
    """A right/remembered choice leaves level and counters untouched."""
    reviewed_at = datetime(2026, 9, 21, 11, 45)
    original = make_card(
        id=1,
        level=Levels.LEVEL_5,
        cnt_shown=7,
        cnt_corr_answers=4,
    )
    service = ReviewService()
    service.session.initialize([original, make_card(id=2)], "Words", 42)
    save_calls = []
    monkeypatch.setattr("app.services.learning.review_service.get_timestamp", lambda: reviewed_at)
    monkeypatch.setattr(
        "app.services.learning.review_service.update_spreadsheet",
        lambda tab, cards, spreadsheet_id: save_calls.append(cards),
    )

    result = service.record_review(ReviewOutcome.REMEMBERED, spreadsheet_id="sheet-123")

    assert result.success is True
    assert save_calls == []
    state = service.session.get_state()
    reviewed_card = service.session.deserialize_card(state.cards[0])
    assert reviewed_card.level == Levels.LEVEL_5
    assert reviewed_card.cnt_shown == 7
    assert reviewed_card.cnt_corr_answers == 4
    assert reviewed_card.last_shown == reviewed_at


def test_last_review_completes_and_clears_the_stack(request_context, monkeypatch):
    """The final choice saves the complete stack once and ends the session."""
    service = ReviewService()
    service.session.initialize(
        [make_card(id=1, level=Levels.LEVEL_3), make_card(id=2, level=Levels.LEVEL_5)],
        "Words",
        42,
    )
    saved_batches = []
    monkeypatch.setattr(
        "app.services.learning.review_service.update_spreadsheet",
        lambda tab, cards, spreadsheet_id: saved_batches.append((tab, cards, spreadsheet_id)),
    )

    first_result = service.record_review(ReviewOutcome.FORGOTTEN, "sheet-123")
    result = service.record_review(ReviewOutcome.REMEMBERED, "sheet-123")

    assert first_result.completed is False
    assert result.success is True
    assert result.completed is True
    assert len(saved_batches) == 1
    tab, cards, spreadsheet_id = saved_batches[0]
    assert tab == "Words"
    assert spreadsheet_id == "sheet-123"
    assert [card.level for card in cards] == [Levels.LEVEL_2, Levels.LEVEL_5]
    assert service.has_active_session() is False


def test_failed_save_keeps_current_card_and_level(request_context, monkeypatch):
    """A final batch failure keeps prior choices and leaves the last card retryable."""
    service = ReviewService()
    service.session.initialize(
        [
            make_card(id=1, level=Levels.LEVEL_3),
            make_card(id=2, level=Levels.LEVEL_3),
        ],
        "Words",
        42,
    )

    def fail_save(*args, **kwargs):
        raise RuntimeError("Sheets unavailable")

    monkeypatch.setattr("app.services.learning.review_service.update_spreadsheet", fail_save)

    first_result = service.record_review(ReviewOutcome.FORGOTTEN, spreadsheet_id="sheet-123")
    result = service.record_review(ReviewOutcome.FORGOTTEN, spreadsheet_id="sheet-123")

    assert first_result.success is True
    assert result.success is False
    state = service.session.get_state()
    assert state.current_index == 1
    assert service.session.deserialize_card(state.cards[0]).level == Levels.LEVEL_2
    assert service.session.deserialize_card(state.cards[1]).level == Levels.LEVEL_3


def test_end_session_early_saves_only_reviewed_cards(request_context, monkeypatch):
    """Ending early batch-saves cards before the current unreviewed card."""
    service = ReviewService()
    service.session.initialize(
        [make_card(id=1, level=Levels.LEVEL_3), make_card(id=2, level=Levels.LEVEL_5)],
        "Words",
        42,
    )
    saved_batches = []
    monkeypatch.setattr(
        "app.services.learning.review_service.update_spreadsheet",
        lambda tab, cards, spreadsheet_id: saved_batches.append((tab, cards, spreadsheet_id)),
    )
    service.record_review(ReviewOutcome.FORGOTTEN, "sheet-123")

    result = service.end_session_early("sheet-123")

    assert result.success is True
    assert result.completed is True
    assert len(saved_batches) == 1
    tab, cards, spreadsheet_id = saved_batches[0]
    assert tab == "Words"
    assert spreadsheet_id == "sheet-123"
    assert [card.id for card in cards] == [1]
    assert cards[0].level == Levels.LEVEL_2
    assert service.has_active_session() is False


def test_end_session_early_without_reviews_skips_sheet_write(request_context, monkeypatch):
    """Ending before the first choice clears the session without an empty API write."""
    service = ReviewService()
    service.session.initialize([make_card()], "Words", 42)
    save_calls = []
    monkeypatch.setattr(
        "app.services.learning.review_service.update_spreadsheet",
        lambda *args, **kwargs: save_calls.append((args, kwargs)),
    )

    result = service.end_session_early("sheet-123")

    assert result.success is True
    assert save_calls == []
    assert service.has_active_session() is False


def test_failed_early_end_keeps_review_session(request_context, monkeypatch):
    """A failed partial batch write leaves reviewed progress available to retry."""
    service = ReviewService()
    service.session.initialize([make_card(id=1), make_card(id=2)], "Words", 42)
    service.record_review(ReviewOutcome.REMEMBERED, "sheet-123")

    def fail_save(*args, **kwargs):
        raise RuntimeError("Sheets unavailable")

    monkeypatch.setattr("app.services.learning.review_service.update_spreadsheet", fail_save)

    result = service.end_session_early("sheet-123")

    assert result.success is False
    assert service.has_active_session() is True
    assert service.session.get_current_index() == 1
