"""Focused tests for OAuth access-token refresh decisions."""

from datetime import UTC, datetime, timedelta

from app.services.auth_manager import auth_manager
from app.session_manager import SessionKeys as sk
from app.session_manager import SessionManager as sm


def _set_valid_session_credentials() -> None:
    sm.set(sk.USER_ID, 1)
    sm.set(sk.ACCESS_TOKEN, "current-token")
    sm.set(sk.ACCESS_TOKEN_EXPIRY, datetime.now(UTC) + timedelta(minutes=30))


def test_refresh_boundary_uses_ten_minute_buffer(request_context):
    _set_valid_session_credentials()

    sm.set(sk.ACCESS_TOKEN_EXPIRY, datetime.now(UTC) + timedelta(minutes=11))
    assert auth_manager._needs_token_refresh() is False

    sm.set(sk.ACCESS_TOKEN_EXPIRY, datetime.now(UTC) + timedelta(minutes=9))
    assert auth_manager._needs_token_refresh() is True


def test_proactive_refresh_failure_uses_still_valid_token(request_context, monkeypatch):
    _set_valid_session_credentials()
    monkeypatch.setattr(auth_manager, "_needs_token_refresh", lambda: True)
    monkeypatch.setattr(auth_manager, "_refresh_credentials", lambda user_id: False)

    credentials = auth_manager.get_credentials()

    assert credentials is not None
    assert credentials.token == "current-token"


def test_forced_refresh_failure_does_not_reuse_rejected_token(request_context, monkeypatch):
    _set_valid_session_credentials()
    monkeypatch.setattr(auth_manager, "_refresh_credentials", lambda user_id: False)

    assert auth_manager.get_credentials(force_refresh=True) is None


def test_expired_token_is_rejected_when_refresh_fails(request_context, monkeypatch):
    _set_valid_session_credentials()
    sm.set(sk.ACCESS_TOKEN_EXPIRY, datetime.now(UTC) - timedelta(minutes=1))
    monkeypatch.setattr(auth_manager, "_refresh_credentials", lambda user_id: False)

    assert auth_manager.get_credentials() is None
