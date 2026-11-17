"""Behavior tests for browser login, Google credential refresh, and logout."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from urllib.parse import parse_qs, urlencode, urlsplit

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
def auth_app(tmp_path, monkeypatch, google_oauth):
    monkeypatch.setattr(config, "session_file_dir", str(tmp_path / "sessions"))
    monkeypatch.setattr(config, "encryption_key", Fernet.generate_key().decode())
    monkeypatch.setenv("OAUTHLIB_INSECURE_TRANSPORT", "1")
    app = create_app(google_oauth=google_oauth)
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///:memory:")
    db.init_app(app)
    with app.app_context():
        db.create_all()
    return app


@pytest.fixture
def google_token_request(monkeypatch):
    response = Mock(
        text=json.dumps(
            {
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "id_token": "id-token",
                "expires_in": 3600,
                "token_type": "Bearer",
            }
        ),
        status_code=200,
    )
    request = Mock(return_value=response)
    monkeypatch.setattr("requests_oauthlib.OAuth2Session.request", request)
    return request


@pytest.fixture
def verify_token(monkeypatch):
    verify = Mock(
        return_value={"sub": "google-user", "email": "learner@example.test", "name": "Learner"}
    )
    monkeypatch.setattr("app.services.google_oauth.id_token.verify_oauth2_token", verify)
    return verify


def _start_login(client, **kwargs) -> dict[str, list[str]]:
    login = client.get("/auth", **kwargs)
    assert login.status_code == 302
    authorization_url = urlsplit(login.location)
    assert authorization_url.netloc == "accounts.example.test"
    return parse_qs(authorization_url.query)


def _callback_url(state: str) -> str:
    return "/oauth2callback?" + urlencode({"code": "test-code", "state": state})


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


def test_google_login_creates_user_and_shows_spreadsheet_setup(
    auth_app, google_token_request, verify_token, monkeypatch
):
    read_sheets = Mock()
    monkeypatch.setattr("app.routes.index.read_all_card_sets", read_sheets)
    cookie_name = auth_app.config["SESSION_COOKIE_NAME"]

    with auth_app.test_client() as client:
        assert b"Sign in with Google" in client.get("/").data
        assert sm.has(sk.TEST_SESSION)

        params = _start_login(client, base_url="http://localhost:8080")
        assert params["access_type"] == ["offline"]
        assert params["include_granted_scopes"] == ["true"]
        assert set(params["scope"][0].split()) == set(config.scopes)
        assert params["code_challenge_method"] == ["S256"]
        assert params["code_challenge"][0]
        code_verifier = sm.get(sk.AUTH_CODE_VERIFIER)
        previous_cookie = client.get_cookie(cookie_name).value
        callback_url = _callback_url(params["state"][0])

        callback = client.get(callback_url)

        assert callback.status_code == 302
        assert callback.location == "/"
        assert client.get_cookie(cookie_name).value != previous_cookie
        assert not sm.has(sk.TEST_SESSION)
        user = auth_manager.user
        assert (user.google_user_id, user.email, user.name) == (
            "google-user",
            "learner@example.test",
            "Learner",
        )
        assert not sm.has(sk.AUTH_STATE)
        assert not sm.has(sk.AUTH_REDIRECT_URI)
        assert not sm.has(sk.AUTH_CODE_VERIFIER)
        token = db.session.get(RefreshToken, sm.get(sk.REFRESH_TOKEN_ID))
        assert token.user_id == user.id
        assert token.get_decrypted_token() == "refresh-token"
        assert b"Set Up Your Learning Spreadsheet" in client.get(callback.location).data
        assert b"OAuth callback error" in client.get(callback_url).data
        assert auth_manager.is_authenticated()

    old_browser = auth_app.test_client()
    old_browser.set_cookie(cookie_name, previous_cookie)
    assert b"OAuth callback error" in old_browser.get(callback_url).data
    assert b"Sign in with Google" in old_browser.get("/").data

    verify_token.assert_called_once()
    read_sheets.assert_not_called()
    google_token_request.assert_called_once()
    token_data = google_token_request.call_args.kwargs["data"]
    assert token_data["redirect_uri"] == params["redirect_uri"][0]
    assert token_data["redirect_uri"] == "http://localhost:8080/oauth2callback"
    assert len(code_verifier) >= 43
    assert token_data["code_verifier"] == code_verifier


def test_failed_callback_leaves_browser_signed_out(auth_app, google_token_request):
    with auth_app.test_client() as client:
        state = _start_login(client)["state"][0]
        response = client.get("/oauth2callback?error=access_denied&" + urlencode({"state": state}))

        assert b"OAuth callback error" in response.data
        assert not auth_manager.is_authenticated()
        assert auth_manager.user is None
        assert not sm.has(sk.ACCESS_TOKEN)
        assert User.query.count() == 0
        assert RefreshToken.query.count() == 0
    google_token_request.assert_not_called()


@pytest.mark.parametrize("callback_state", ["missing", "empty", "mismatch", "duplicate"])
def test_invalid_callback_state_is_rejected_and_consumed(
    auth_app, google_token_request, callback_state
):
    with auth_app.test_client() as client:
        state = _start_login(client)["state"][0]
        state_queries = {
            "missing": "",
            "empty": "&state=",
            "mismatch": "&state=unexpected",
            "duplicate": "&state=unexpected&" + urlencode({"state": state}),
        }
        invalid = client.get("/oauth2callback?code=test-code" + state_queries[callback_state])
        assert b"OAuth callback error" in invalid.data
        assert not sm.has(sk.AUTH_STATE)

        retry = client.get(_callback_url(state))
        assert b"OAuth callback error" in retry.data
        assert auth_manager.user is None
    google_token_request.assert_not_called()


def test_invalid_id_token_leaves_no_user_or_grant(
    auth_app, google_token_request, verify_token, caplog
):
    verify_token.side_effect = ValueError("provider details")
    with auth_app.test_client() as client:
        state = _start_login(client)["state"][0]
        response = client.get(_callback_url(state))

        assert b"OAuth callback error" in response.data
        assert b"provider details" not in response.data
        assert "provider details" not in caplog.text
        assert "test-code" not in caplog.text
        assert not sm.has(sk.AUTH_STATE)
        assert auth_manager.user is None
        assert User.query.count() == 0
        assert RefreshToken.query.count() == 0
    google_token_request.assert_called_once()


def test_google_login_updates_existing_user_by_google_subject(
    auth_app, google_token_request, verify_token
):
    with auth_app.app_context():
        user = _add_user("google-user")
        user_id = user.id
        _add_user("another-google-user").email = "learner@example.test"
        db.session.commit()

    with auth_app.test_client() as client:
        state = _start_login(client)["state"][0]
        assert client.get(_callback_url(state)).location == "/"
        assert auth_manager.user.id == user_id
        assert auth_manager.user.email == "learner@example.test"
        assert User.query.count() == 2
    google_token_request.assert_called_once()
    verify_token.assert_called_once()


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
