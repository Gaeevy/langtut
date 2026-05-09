"""API tests for listening cards endpoint."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.auth_manager import auth_manager


def _patch_auth(monkeypatch, authenticated: bool, spreadsheet_id: str | None = "sheet-1") -> None:
    """Patch authentication and current user in one place."""
    monkeypatch.setattr(auth_manager, "is_authenticated", lambda: authenticated)
    if spreadsheet_id is None:
        user = SimpleNamespace(get_active_spreadsheet=lambda: None)
    else:
        user = SimpleNamespace(
            get_active_spreadsheet=lambda: SimpleNamespace(spreadsheet_id=spreadsheet_id)
        )
    monkeypatch.setattr(type(auth_manager), "user", property(lambda self: user))


def _card(card_id: int, word: str | None, example: str | None) -> SimpleNamespace:
    return SimpleNamespace(id=card_id, word=word, example=example)


def test_get_cards_requires_authentication(client, monkeypatch):
    """Endpoint returns JSON 401 for unauthenticated requests."""
    _patch_auth(monkeypatch, authenticated=False)

    response = client.get("/api/cards/AnyTab")
    assert response.status_code == 401
    payload = response.get_json()
    assert payload["success"] is False
    assert payload["error"] == "Unauthorized"


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
def test_get_cards_error_partitions(
    client, monkeypatch, spreadsheet_id, card_set, expected_status: int, error_fragment: str
):
    """MECE error matrix for missing sheet, missing set, empty set, and invalid cards."""
    _patch_auth(monkeypatch, authenticated=True, spreadsheet_id=spreadsheet_id)
    monkeypatch.setattr(
        "app.services.listening_cards_service.read_card_set", lambda **kwargs: card_set
    )

    response = client.get("/api/cards/Daily")
    assert response.status_code == expected_status
    payload = response.get_json()
    assert set(payload.keys()) == {"success", "error"}
    assert payload["success"] is False
    assert error_fragment in payload["error"]


def test_get_cards_returns_filtered_shuffled_payload(client, monkeypatch):
    """Valid cards are filtered, shuffled, and returned with counts."""
    _patch_auth(monkeypatch, authenticated=True, spreadsheet_id="sheet-42")

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

    response = client.get("/api/cards/Daily")
    assert response.status_code == 200

    payload = response.get_json()
    assert set(payload.keys()) == {
        "success",
        "tab_name",
        "sheet_gid",
        "cards",
        "total_count",
        "original_count",
    }
    assert payload["success"] is True
    assert payload["tab_name"] == "Daily"
    assert payload["sheet_gid"] == 991
    assert payload["original_count"] == 3
    assert payload["total_count"] == 2
    assert payload["cards"] == [
        {"id": 3, "word": "adeus", "example": "até logo"},
        {"id": 1, "word": "ola", "example": "exemplo"},
    ]


def test_get_cards_handles_unexpected_exception(client, monkeypatch):
    """Unexpected backend errors are converted into 500 JSON responses."""
    _patch_auth(monkeypatch, authenticated=True)

    def _boom(**kwargs):
        raise RuntimeError("gsheet down")

    monkeypatch.setattr("app.services.listening_cards_service.read_card_set", _boom)

    response = client.get("/api/cards/Daily")
    assert response.status_code == 500
    payload = response.get_json()
    assert set(payload.keys()) == {"success", "error"}
    assert payload["success"] is False
    assert "Failed to fetch cards" in payload["error"]
