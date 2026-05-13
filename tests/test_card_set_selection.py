"""Tests for CardSet review selection."""

from datetime import datetime, timedelta

import pytest

from app.models import Card, CardSet, Levels


def _delayed_card(cid: int, level: Levels = Levels.LEVEL_0) -> Card:
    """Build a card that is due now (level 0 => next_review == last_shown)."""
    return Card(
        id=cid,
        word=f"w{cid}",
        translation=f"t{cid}",
        equivalent="",
        example="",
        example_translation="",
        cnt_shown=1,
        cnt_corr_answers=0,
        level=level,
        last_shown=datetime.now() - timedelta(days=1),
    )


def test_get_cards_to_review_shuffles_full_pool_before_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Due cards are shuffled before applying max count (not overdue-sorted first)."""
    cards = [_delayed_card(i) for i in range(1, 6)]

    def reverse_shuffle(lst: list) -> None:
        lst.reverse()

    monkeypatch.setattr("app.models.random.shuffle", reverse_shuffle)

    card_set = CardSet(name="tab", gid=1, cards=cards)
    result = card_set.get_cards_to_review(limit=2, ignore_unshown=False)

    assert len(result) == 2
    assert {c.id for c in result} == {5, 4}
