"""Behavior tests for browser login, Google credential refresh, and logout."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from cryptography.fernet import Fernet
from google.oauth2.credentials import Credentials

from app import create_app
from app.config import config
from app.database import RefreshToken, User, db
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


@pytest.fixture
def auth_app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "session_file_dir", str(tmp_path / "sessions"))
    monkeypatch.setattr(config, "encryption_key", Fernet.generate_key().decode())
    app = create_app()
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///:memory:")
    db.init_app(app)
    with app.app_context():
        db.create_all()
    return app


@pytest.fixture
def google_flow(monkeypatch):
    flow = Mock()
    flow.authorization_url.return_value = ("https://accounts.example.test/authorize", "state")
    flow.credentials = Credentials(
        token="access-token",
        refresh_token="refresh-token",
        id_token="id-token",
        expiry=datetime.now(UTC) + timedelta(hours=1),
    )
    monkeypatch.setattr(
        "app.services.auth_manager.Flow.from_client_secrets_file", Mock(return_value=flow)
    )
    return flow


def _add_user(google_user_id: str) -> User:
    user = User(google_user_id=google_user_id, email=f"{google_user_id}@example.test")
    db.session.add(user)
    db.session.flush()
    return user


def _add_refresh_token(user: User, value: str, last_used: datetime) -> RefreshToken:
    token = RefreshToken(user_id=user.id, last_used=last_used)
    token.encrypt_and_store(value)
    db.session.add(token)
    db.session.flush()
    return token


def test_google_login_creates_user_and_shows_spreadsheet_setup(auth_app, google_flow, monkeypatch):
    verify_token = Mock(
        return_value={"sub": "google-user", "email": "learner@example.test", "name": "Learner"}
    )
    read_sheets = Mock()
    monkeypatch.setattr("app.services.auth_manager.id_token.verify_oauth2_token", verify_token)
    monkeypatch.setattr("app.routes.index.read_all_card_sets", read_sheets)

    with auth_app.test_client() as client:
        assert b"Sign in with Google" in client.get("/").data

        login = client.get("/auth")
        assert login.status_code == 302
        assert login.location == "https://accounts.example.test/authorize"
        google_flow.authorization_url.assert_called_once_with(
            access_type="offline", include_granted_scopes="true"
        )

        callback = client.get("/oauth2callback?code=example&state=state", follow_redirects=True)

        assert callback.status_code == 200
        assert b"Set Up Your Learning Spreadsheet" in callback.data
        user = auth_manager.user
        assert (user.google_user_id, user.email, user.name) == (
            "google-user",
            "learner@example.test",
            "Learner",
        )
        assert not sm.has(sk.AUTH_STATE)
        assert not sm.has(sk.AUTH_REDIRECT_URI)
        token = db.session.get(RefreshToken, sm.get(sk.REFRESH_TOKEN_ID))
        assert token.user_id == user.id
        assert token.get_decrypted_token() == google_flow.credentials.refresh_token
    verify_token.assert_called_once()
    read_sheets.assert_not_called()


def test_failed_callback_leaves_browser_signed_out(auth_app, google_flow):
    google_flow.fetch_token.side_effect = ValueError("Google denied authorization")

    with auth_app.test_client() as client:
        client.get("/auth")
        response = client.get("/oauth2callback?error=access_denied&state=state")

        assert b"OAuth callback error" in response.data
        assert not auth_manager.is_authenticated()
        assert auth_manager.user is None
        assert not sm.has(sk.ACCESS_TOKEN)
        assert User.query.count() == 0
        assert RefreshToken.query.count() == 0


@pytest.mark.parametrize("deleted_user", [False, True], ids=["anonymous", "deleted-user"])
def test_user_lookup_can_differ_from_credential_based_authentication(auth_app, deleted_user):
    with auth_app.test_request_context():
        if deleted_user:
            _set_valid_session_credentials()
            user = _add_user("deleted-user")
            sm.set(sk.USER_ID, user.id)
            db.session.commit()
            db.session.delete(user)
            db.session.commit()

        assert auth_manager.user is None
        assert auth_manager.is_authenticated() is deleted_user


@pytest.mark.parametrize("preferred_owner", ["current-user", "other-user"])
def test_refresh_uses_only_tokens_owned_by_session_user(auth_app, monkeypatch, preferred_owner):
    def refresh(credentials, request):
        assert credentials.refresh_token == expected_token
        credentials.token = "refreshed-access-token"
        credentials.expiry = datetime.now(UTC) + timedelta(hours=1)

    monkeypatch.setattr(Credentials, "refresh", refresh)
    with auth_app.test_request_context():
        current_user = _add_user("current-user")
        other_user = _add_user("other-user")
        now = datetime.now(UTC)
        older = _add_refresh_token(current_user, "older-token", now - timedelta(days=1))
        _add_refresh_token(current_user, "newer-token", now - timedelta(hours=1))
        foreign = _add_refresh_token(other_user, "other-users-token", now)
        db.session.commit()
        preferred, expected_token = (
            (older, "older-token")
            if preferred_owner == "current-user"
            else (foreign, "newer-token")
        )
        sm.set(sk.USER_ID, current_user.id)
        sm.set(sk.REFRESH_TOKEN_ID, preferred.id)

        credentials = auth_manager.get_credentials(force_refresh=True)

        assert credentials is not None
        assert credentials.token == "refreshed-access-token"


@pytest.mark.parametrize(
    ("logout_all_devices", "preferred_owner", "remaining_devices"),
    [
        (False, "current-user", {"second-device", "other-users-device"}),
        (False, "other-user", {"current-device", "second-device", "other-users-device"}),
        (True, "current-user", {"other-users-device"}),
    ],
)
def test_logout_clears_session_and_deletes_only_selected_owned_tokens(
    auth_app, logout_all_devices, preferred_owner, remaining_devices
):
    with auth_app.test_request_context():
        current_user = _add_user("current-user")
        other_user = _add_user("other-user")
        now = datetime.now(UTC)
        current_token = _add_refresh_token(current_user, "current-device", now)
        _add_refresh_token(current_user, "second-device", now)
        foreign = _add_refresh_token(other_user, "other-users-device", now)
        db.session.commit()
        _set_valid_session_credentials()
        sm.set(sk.USER_ID, current_user.id)
        preferred = current_token if preferred_owner == "current-user" else foreign
        sm.set(sk.REFRESH_TOKEN_ID, preferred.id)
        sm.set(sk.LEARNING_ACTIVE_TAB, "Vocabulary")
        sm.set(sk.REVIEW_ACTIVE_TAB, "Review")

        auth_manager.logout(logout_all_devices=logout_all_devices)

        assert not auth_manager.is_authenticated()
        assert auth_manager.user is None
        assert not sm.has(sk.ACCESS_TOKEN)
        assert not sm.has(sk.REFRESH_TOKEN_ID)
        assert not sm.has(sk.LEARNING_ACTIVE_TAB)
        assert sm.get(sk.REVIEW_ACTIVE_TAB) == "Review"
        assert {token.get_decrypted_token() for token in RefreshToken.query.all()} == (
            remaining_devices
        )
