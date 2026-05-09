"""Unit tests for ListeningCardsService."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.listening_cards_service import ListeningCardsService


def _card(card_id: int, word: str | None, example: str | None) -> SimpleNamespace:
    return SimpleNamespace(id=card_id, word=word, example=example)


def _user(spreadsheet_id: str | None) -> SimpleNamespace:
    if spreadsheet_id is None:
        return SimpleNamespace(get_active_spreadsheet=lambda: None)
    return SimpleNamespace(
        get_active_spreadsheet=lambda: SimpleNamespace(spreadsheet_id=spreadsheet_id)
    )


@pytest.mark.parametrize(
    ("spreadsheet_id", "card_set", "expected_status", "error_fragment"),
    [
        (None, None, 400, "No spreadsheet configured"),
        ("sheet-1", None, 404, 'Card set "Daily" not found'),
        (
            "sheet-1",
            SimpleNamespace(name="Daily", gid=1, cards=[]),
            400,
            'Card set "Daily" is empty',
        ),
        (
            "sheet-1",
            SimpleNamespace(
                name="Daily",
                gid=2,
                cards=[_card(1, None, "x"), _card(2, "ola", " "), _card(3, " ", "abc")],
            ),
            400,
            "No cards with audio content",
        ),
    ],
)
def test_get_for_listening_error_matrix(
    monkeypatch, spreadsheet_id, card_set, expected_status: int, error_fragment: str
):
    service = ListeningCardsService()
    monkeypatch.setattr(
        "app.services.listening_cards_service.read_card_set", lambda **kwargs: card_set
    )

    result = service.get_for_listening(_user(spreadsheet_id), "Daily")
    assert result.status_code == expected_status
    assert result.payload["success"] is False
    assert error_fragment in result.payload["error"]


def test_get_for_listening_success_payload(monkeypatch):
    service = ListeningCardsService()
    card_set = SimpleNamespace(
        name="Daily",
        gid=991,
        cards=[
            _card(1, " ola ", " exemplo "),
            _card(2, "obrigado", ""),
            _card(3, "adeus", "até logo"),
        ],
    )
    monkeypatch.setattr(
        "app.services.listening_cards_service.read_card_set", lambda **kwargs: card_set
    )
    monkeypatch.setattr(
        "app.services.listening_cards_service.random.shuffle", lambda items: items.reverse()
    )

    result = service.get_for_listening(_user("sheet-42"), "Daily")
    assert result.status_code == 200
    assert result.payload == {
        "success": True,
        "tab_name": "Daily",
        "sheet_gid": 991,
        "cards": [
            {"id": 3, "word": "adeus", "example": "até logo"},
            {"id": 1, "word": "ola", "example": "exemplo"},
        ],
        "total_count": 2,
        "original_count": 3,
    }
