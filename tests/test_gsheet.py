"""Tests for gsheet integration helpers."""

from __future__ import annotations

from types import SimpleNamespace

import gspread
import pytest
from gspread.exceptions import APIError
from requests import Response

from app import gsheet
from app.models import CardSet
from tests.conftest import make_card


def _api_error(status_code: int) -> APIError:
    response = Response()
    response.status_code = status_code
    response._content = (
        f'{{"error": {{"code": {status_code}, "message": "failure", "status": "ERROR"}}}}'
    ).encode()
    return APIError(response)


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


def test_get_spreadsheet_forces_refresh_and_retries_once_after_401(monkeypatch):
    credential_calls = []
    open_calls = 0
    spreadsheet = object()

    def get_credentials(*, force_refresh=False):
        credential_calls.append(force_refresh)
        return "refreshed" if force_refresh else "initial"

    def open_by_key(sheet_id):
        nonlocal open_calls
        open_calls += 1
        if open_calls == 1:
            raise _api_error(401)
        return spreadsheet

    monkeypatch.setattr("app.gsheet.auth_manager.get_credentials", get_credentials)
    monkeypatch.setattr(
        "app.gsheet.gspread.authorize",
        lambda credentials: SimpleNamespace(open_by_key=open_by_key),
    )

    assert gsheet.get_spreadsheet("sheet-id") is spreadsheet
    assert credential_calls == [False, True]
    assert open_calls == 2


def test_update_spreadsheet_retries_batch_once_after_401(monkeypatch):
    card = make_card()
    card_set = CardSet(name="Tab1", gid=1, cards=[card.model_copy(deep=True)])
    credential_calls = []

    def authorize(credentials):
        def batch_update(updates):
            if credentials == "initial":
                raise _api_error(401)
            return "saved"

        worksheet = SimpleNamespace(batch_update=batch_update)
        spreadsheet = SimpleNamespace(worksheet=lambda name: worksheet)
        return SimpleNamespace(open_by_key=lambda sheet_id: spreadsheet)

    monkeypatch.setattr("app.gsheet.read_card_set", lambda name, sheet_id: card_set)
    monkeypatch.setattr(
        "app.gsheet.auth_manager.get_credentials",
        lambda *, force_refresh=False: credential_calls.append(force_refresh)
        or ("refreshed" if force_refresh else "initial"),
    )
    monkeypatch.setattr("app.gsheet.gspread.authorize", authorize)

    assert gsheet.update_spreadsheet("Tab1", [card], "sheet-id") == "saved"
    assert credential_calls == [False, True]


def test_get_spreadsheet_does_not_retry_non_authentication_error(monkeypatch):
    credential_calls = []

    def get_credentials(*, force_refresh=False):
        credential_calls.append(force_refresh)
        return object()

    monkeypatch.setattr("app.gsheet.auth_manager.get_credentials", get_credentials)
    monkeypatch.setattr(
        "app.gsheet.gspread.authorize",
        lambda credentials: SimpleNamespace(
            open_by_key=lambda sheet_id: (_ for _ in ()).throw(_api_error(500))
        ),
    )

    assert gsheet.get_spreadsheet("sheet-id") is None
    assert credential_calls == [False]
