"""Access boundaries for retired administration and protected diagnostic/audio routes."""

from unittest.mock import Mock

import pytest

from app.routes.api.tts import tts_service
from app.services.auth_manager import auth_manager


@pytest.mark.parametrize("authenticated", [False, True])
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/admin/db-info"),
        ("GET", "/admin/users"),
        ("GET", "/admin/spreadsheets"),
        ("GET", "/admin/user/1"),
        ("GET", "/admin/export-db"),
        ("POST", "/admin/query"),
        ("GET", "/admin/volume-check"),
        ("GET", "/admin/table-info"),
        ("GET", "/admin/railway-debug"),
    ],
)
def test_retired_admin_routes_return_not_found(client, monkeypatch, authenticated, method, path):
    monkeypatch.setattr(auth_manager, "is_authenticated", lambda: authenticated)
    assert client.open(path, method=method).status_code == 404


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/api/tts/status"), ("POST", "/api/tts/speak"), ("GET", "/test")],
)
def test_anonymous_requests_cannot_run_audio_or_diagnostics(client, monkeypatch, method, path):
    monkeypatch.setattr(auth_manager, "is_authenticated", lambda: False)
    synthesize = Mock()
    read_sheets = Mock()
    monkeypatch.setattr(tts_service, "text_to_speech", synthesize)
    monkeypatch.setattr("app.routes.test.read_all_card_sets", read_sheets)

    response = client.open(path, method=method, json={"text": "olá"})

    assert response.status_code == 401
    assert response.get_json() == {"success": False, "error": "Unauthorized"}
    synthesize.assert_not_called()
    read_sheets.assert_not_called()


def test_anonymous_audio_test_page_redirects_to_login(client, monkeypatch):
    monkeypatch.setattr(auth_manager, "is_authenticated", lambda: False)
    response = client.get("/test-tts")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth")


def test_authenticated_audio_generation_still_works(client, monkeypatch):
    monkeypatch.setattr(auth_manager, "is_authenticated", lambda: True)
    synthesize = Mock(return_value="encoded-audio")
    monkeypatch.setattr(tts_service, "text_to_speech", synthesize)

    response = client.post("/api/tts/speak", json={"text": "olá"})

    assert response.status_code == 200
    assert response.get_json() == {"success": True, "audio_base64": "encoded-audio"}
    synthesize.assert_called_once_with(text="olá", spreadsheet_id=None, sheet_gid=None)
