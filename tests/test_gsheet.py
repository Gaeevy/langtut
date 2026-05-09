"""Tests for gsheet integration helpers."""

from __future__ import annotations

from types import SimpleNamespace

import gspread
import pytest

from app import gsheet


def test_get_spreadsheet_returns_none_without_credentials(monkeypatch):
    monkeypatch.setattr("app.gsheet.auth_manager.get_credentials", lambda: None)
    assert gsheet.get_spreadsheet("sheet-id") is None


@pytest.mark.parametrize(
    ("error",),
    [
        (gspread.SpreadsheetNotFound("missing"),),
        (gspread.WorksheetNotFound("missing"),),
    ],
)
def test_lookup_helpers_return_none_on_known_gspread_errors(monkeypatch, error):
    fake_spreadsheet = SimpleNamespace(
        worksheet=lambda name: (_ for _ in ()).throw(error),
    )
    monkeypatch.setattr("app.gsheet.auth_manager.get_credentials", lambda: object())
    monkeypatch.setattr(
        "app.gsheet.gspread.authorize",
        lambda creds: SimpleNamespace(open_by_key=lambda sid: fake_spreadsheet),
    )

    if isinstance(error, gspread.SpreadsheetNotFound):
        monkeypatch.setattr(
            "app.gsheet.gspread.authorize",
            lambda creds: SimpleNamespace(
                open_by_key=lambda sid: (_ for _ in ()).throw(gspread.SpreadsheetNotFound("x"))
            ),
        )
        assert gsheet.get_spreadsheet("sheet-id") is None
    else:
        assert gsheet.get_worksheet("Tab1", "sheet-id") is None
