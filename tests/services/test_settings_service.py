"""Unit tests for SettingsService."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.settings_service import SettingsService


def test_validate_spreadsheet_requires_url():
    service = SettingsService()
    result = service.validate_spreadsheet(SimpleNamespace(), "")
    assert result.status_code == 200
    assert result.payload == {"success": False, "error": "Spreadsheet URL is required"}


def test_validate_spreadsheet_rejects_invalid_url(monkeypatch):
    service = SettingsService()
    monkeypatch.setattr("app.services.settings_service.extract_spreadsheet_id", lambda _: "")
    result = service.validate_spreadsheet(SimpleNamespace(), "bad")
    assert result.payload == {"success": False, "error": "Invalid spreadsheet URL"}


def test_validate_spreadsheet_returns_payload(monkeypatch):
    service = SettingsService()
    monkeypatch.setattr(
        "app.services.settings_service.extract_spreadsheet_id", lambda _: "sheet123"
    )
    monkeypatch.setattr(
        "app.services.settings_service.validate_spreadsheet_access", lambda _: "Sheet Name"
    )
    monkeypatch.setattr(
        "app.services.settings_service.read_all_card_sets",
        lambda _: [SimpleNamespace(name="Tab1", cards=[1, 2])],
    )
    user = SimpleNamespace(
        add_spreadsheet=lambda sid, url, name: SimpleNamespace(
            id=7,
            spreadsheet_id=sid,
            spreadsheet_name=name,
            spreadsheet_url=url,
            is_active=True,
        )
    )

    result = service.validate_spreadsheet(user, "https://docs.google.com/spreadsheets/d/sheet123")
    assert result.payload["success"] is True
    assert result.payload["spreadsheet"]["spreadsheet_id"] == "sheet123"
    assert result.payload["spreadsheet"]["spreadsheet_name"] == "Sheet Name"
    assert result.payload["card_sets"] == [{"name": "Tab1", "card_count": 2}]


@pytest.mark.parametrize(
    ("method_name", "error_message"),
    [
        ("set_spreadsheet", "Spreadsheet ID is required"),
        ("activate_spreadsheet", "Spreadsheet ID is required"),
        ("rename_spreadsheet", "Spreadsheet ID is required"),
        ("remove_spreadsheet", "Spreadsheet ID is required"),
    ],
)
def test_id_based_operations_require_id(method_name: str, error_message: str):
    service = SettingsService()
    method = getattr(service, method_name)
    user = SimpleNamespace()
    args = (user, "") if method_name != "rename_spreadsheet" else (user, "", "name")
    result = method(*args)
    assert result.payload == {"success": False, "error": error_message}
