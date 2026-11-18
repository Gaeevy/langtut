"""Behavior tests for browser login and the Google Sheets connection lifecycle."""

import json
import re
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from cryptography.fernet import Fernet
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from requests.exceptions import ConnectionError

from app import create_app
from app.config import config
from app.database import GoogleSheetsConnection, RefreshToken, User, db
from app.services.auth_manager import auth_manager
from app.services.google_credentials import GoogleConnectionRequiredError
from app.session_manager import SessionKeys as sk
from app.session_manager import SessionManager as sm


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


def _sign_in(client) -> None:
    state = _start_login(client)["state"][0]
    assert client.get(_callback_url(state)).location == "/"


def _csrf_token(client) -> str:
    response = client.get("/")
    assert response.status_code == 200
    return re.search(rb'name="csrf_token" value="([^"]+)"', response.data)[1].decode()


def _start_connection(client) -> dict[str, list[str]]:
    response = client.post("/connect-google-sheets", data={"csrf_token": _csrf_token(client)})
    assert response.status_code == 302
    return parse_qs(urlsplit(response.location).query)


def _connect(client) -> None:
    state = _start_connection(client)["state"][0]
    assert client.get(_callback_url(state)).location == "/"


def test_google_login_requests_identity_and_creates_session_without_sheets(
    auth_app, google_token_request, verify_token, monkeypatch
):
    read_sheets = Mock()
    monkeypatch.setattr("app.routes.index.read_all_card_sets", read_sheets)
    cookie_name = auth_app.config["SESSION_COOKIE_NAME"]

    with auth_app.test_client() as client:
        assert b"Sign in with Google" in client.get("/").data
        assert sm.has(sk.TEST_SESSION)

        params = _start_login(client, base_url="http://localhost:8080")
        assert params["access_type"] == ["online"]
        assert "include_granted_scopes" not in params
        assert set(params["scope"][0].split()) == set(config.google_identity_scopes)
        assert params["code_challenge_method"] == ["S256"]
        assert params["code_challenge"][0]
        code_verifier = sm.get(sk.AUTH_TRANSACTIONS)[params["state"][0]]["code_verifier"]
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
        assert sm.get(sk.AUTH_TRANSACTIONS) == {}
        assert user.google_sheets_connection is None
        assert RefreshToken.query.count() == 0
        assert b"Google Sheets is disconnected" in client.get(callback.location).data
        assert b"Google authorization failed" in client.get(callback_url).data
        assert auth_manager.is_authenticated()

    old_browser = auth_app.test_client()
    old_browser.set_cookie(cookie_name, previous_cookie)
    assert b"Google authorization failed" in old_browser.get(callback_url).data
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

        assert b"Google authorization failed" in response.data
        assert not auth_manager.is_authenticated()
        assert auth_manager.user is None
        assert not sm.has(sk.LOGIN_EXPIRES_AT)
        assert User.query.count() == 0
        assert GoogleSheetsConnection.query.count() == 0
    google_token_request.assert_not_called()


@pytest.mark.parametrize("callback_state", ["missing", "empty", "mismatch", "duplicate"])
def test_invalid_callback_state_preserves_pending_legitimate_attempt(
    auth_app, google_token_request, verify_token, callback_state
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
        assert b"Google authorization failed" in invalid.data
        assert state in sm.get(sk.AUTH_TRANSACTIONS)
        retry = client.get(_callback_url(state))
        assert retry.location == "/"
        assert auth_manager.is_authenticated()
    google_token_request.assert_called_once()


def test_invalid_id_token_leaves_no_user_or_grant(
    auth_app, google_token_request, verify_token, caplog
):
    verify_token.side_effect = ValueError("provider details")
    with auth_app.test_client() as client:
        state = _start_login(client)["state"][0]
        response = client.get(_callback_url(state))

        assert b"Google authorization failed" in response.data
        assert b"provider details" not in response.data
        assert "provider details" not in caplog.text
        assert "test-code" not in caplog.text
        assert not sm.get(sk.AUTH_TRANSACTIONS)
        assert auth_manager.user is None
        assert User.query.count() == 0
        assert GoogleSheetsConnection.query.count() == 0
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


@pytest.mark.parametrize("invalid_session", ["legacy", "deleted-user"])
def test_legacy_sessions_and_deleted_users_require_sign_in(
    auth_app, google_token_request, verify_token, invalid_session
):
    client = auth_app.test_client()
    if invalid_session == "legacy":
        with client.session_transaction() as session:
            session[sk.USER_ID.value] = 1
            session["auth.access_token"] = "legacy-access-token"
    else:
        _sign_in(client)
        with auth_app.app_context():
            db.session.delete(User.query.one())
            db.session.commit()

    assert client.get("/api/verbs/tenses").status_code == 401
    assert client.get("/verbs").location == "/auth"
    assert b"Sign in with Google" in client.get("/").data


def test_login_expires_after_seven_days_without_sliding(
    auth_app, google_token_request, verify_token, monkeypatch
):
    clock = Mock(return_value=1_700_000_000)
    monkeypatch.setattr("app.services.auth_manager.time", clock)
    client = auth_app.test_client()
    _sign_in(client)

    clock.return_value += 7 * 24 * 60 * 60 - 1
    assert client.get("/api/verbs/tenses").status_code == 200
    clock.return_value += 1
    assert client.get("/api/verbs/tenses").status_code == 401
    assert client.get("/verbs").location == "/auth"


@pytest.mark.parametrize(
    "path", ["/clear", "/logout-everywhere", "/disconnect-google-sheets", "/connect-google-sheets"]
)
def test_account_mutations_require_post_and_csrf(
    auth_app, google_token_request, verify_token, path
):
    client = auth_app.test_client()
    _sign_in(client)
    _connect(client)

    assert client.get(path).status_code == 405
    assert client.post(path).status_code == 400
    assert client.post(path, data={"csrf_token": "wrong"}).status_code == 400
    assert client.get("/api/verbs/tenses").status_code == 200
    with auth_app.app_context():
        assert GoogleSheetsConnection.query.count() == 1
        assert User.query.one().session_version == 0


@pytest.mark.parametrize(
    ("path", "other_browser_status", "remaining_version"),
    [("/clear", 200, 0), ("/logout-everywhere", 401, 1)],
)
def test_logout_preserves_sheets_and_invalidates_intended_browser_sessions(
    auth_app, google_token_request, verify_token, path, other_browser_status, remaining_version
):
    device = auth_app.test_client()
    other_device = auth_app.test_client()
    _sign_in(device)
    _sign_in(other_device)
    _connect(device)
    with device.session_transaction() as session:
        session[sk.LEARNING_ACTIVE_TAB.value] = "Vocabulary"
        session[sk.REVIEW_ACTIVE_TAB.value] = "Review"

    response = device.post(path, data={"csrf_token": _csrf_token(device)})

    assert response.location == "/"
    assert device.get("/api/verbs/tenses").status_code == 401
    assert other_device.get("/api/verbs/tenses").status_code == other_browser_status
    with device.session_transaction() as session:
        assert sk.LEARNING_ACTIVE_TAB.value not in session
        assert sk.REVIEW_ACTIVE_TAB.value not in session
    with auth_app.app_context():
        assert User.query.one().session_version == remaining_version
        assert GoogleSheetsConnection.query.one().get_decrypted_token() == "refresh-token"


def test_disconnect_keeps_both_browsers_signed_in_without_google_calls(
    auth_app, google_token_request, verify_token
):
    device = auth_app.test_client()
    other_device = auth_app.test_client()
    _sign_in(device)
    _sign_in(other_device)
    _connect(device)
    csrf_token = _csrf_token(device)
    with auth_app.app_context():
        user = User.query.one()
        user.add_spreadsheet("synthetic-sheet")
        user_id = user.id
        service = auth_app.extensions["google_credentials"]
        assert service.get_credentials(user_id).token == "access-token"
    google_token_request.reset_mock()

    with (
        patch("app.routes.index.read_all_card_sets") as read_sheets,
        patch.object(Credentials, "refresh") as refresh,
    ):
        response = device.post(
            "/disconnect-google-sheets", json={}, headers={"X-CSRFToken": csrf_token}
        )

        assert response.location == "/"
        assert b"Google Sheets is disconnected" in device.get("/").data
        assert device.get("/verbs").status_code == 200
        assert other_device.get("/api/verbs/tenses").status_code == 200
        assert b"Google Sheets is disconnected" in other_device.get("/").data
        with auth_app.app_context():
            assert GoogleSheetsConnection.query.count() == 0
            assert User.query.one().get_active_spreadsheet_id() == "synthetic-sheet"
            assert RefreshToken.query.count() == 0
        read_sheets.assert_not_called()
        refresh.assert_not_called()
    google_token_request.assert_not_called()


def test_confirmed_google_revocation_keeps_current_login(
    auth_app, google_token_request, verify_token
):
    with auth_app.test_client() as client:
        _sign_in(client)
        _connect(client)
        service = auth_app.extensions["google_credentials"]
        revoked = RefreshError("revoked", {"error": "invalid_grant"})
        with patch.object(Credentials, "refresh", side_effect=revoked):
            with pytest.raises(GoogleConnectionRequiredError):
                service.get_credentials(auth_manager.user.id, force_refresh=True)

        assert GoogleSheetsConnection.query.count() == 0
        assert auth_manager.is_authenticated()
        assert client.get("/api/verbs/tenses").status_code == 200


def test_successful_google_login_without_refresh_token_has_no_sheets_connection(
    auth_app, google_token_request, verify_token
):
    response = google_token_request.return_value
    payload = json.loads(response.text)
    del payload["refresh_token"]
    response.text = json.dumps(payload)
    client = auth_app.test_client()
    _sign_in(client)

    assert b"Google Sheets is disconnected" in client.get("/").data
    assert client.get("/api/verbs/tenses").status_code == 200
    with auth_app.app_context():
        assert GoogleSheetsConnection.query.count() == 0


def test_explicit_sheets_connection_requests_offline_access_for_same_account(
    auth_app, google_token_request, verify_token
):
    with auth_app.test_client() as client:
        _sign_in(client)
        login_expiry = sm.get(sk.LOGIN_EXPIRES_AT)
        params = _start_connection(client)
        assert params["access_type"] == ["offline"]
        assert params["prompt"] == ["consent"]
        assert params["login_hint"] == ["learner@example.test"]
        assert set(params["scope"][0].split()) == set(
            config.google_identity_scopes + config.google_sheets_scopes
        )
        assert client.get(_callback_url(params["state"][0])).location == "/"
        assert sm.get(sk.LOGIN_EXPIRES_AT) == login_expiry
        assert auth_manager.user.google_sheets_connection.get_decrypted_token() == "refresh-token"
        assert b"Set Up Your Learning Spreadsheet" in client.get("/").data
        assert b"Reconnect Google Sheets" in client.get("/").data


@pytest.mark.parametrize(
    "failure", ["wrong-account", "partial-scopes", "no-refresh-token", "denied", "outage"]
)
def test_failed_connection_preserves_login_and_existing_grant(
    auth_app, google_token_request, verify_token, failure
):
    with auth_app.test_client() as client:
        _sign_in(client)
        _connect(client)
        state = _start_connection(client)["state"][0]
        payload = json.loads(google_token_request.return_value.text)
        payload["refresh_token"] = "replacement-token"
        expected_status = 400
        if failure == "wrong-account":
            verify_token.return_value = {"sub": "other-google-user"}
        elif failure == "partial-scopes":
            payload["scope"] = "openid"
            expected_status = 403
        elif failure == "no-refresh-token":
            del payload["refresh_token"]
            expected_status = 302
        elif failure == "outage":
            expected_status = 503
            google_token_request.side_effect = ConnectionError("private-provider-details")
        google_token_request.return_value.text = json.dumps(payload)
        callback = _callback_url(state)
        if failure == "denied":
            callback = "/oauth2callback?" + urlencode({"state": state, "error": "access_denied"})

        response = client.get(callback)

        assert response.status_code == expected_status
        assert auth_manager.is_authenticated()
        assert auth_manager.user.google_sheets_connection.get_decrypted_token() == "refresh-token"
        assert b"private-provider-details" not in response.data
        assert client.get(_callback_url(state)).status_code == 400
        assert client.get("/api/verbs/tenses").status_code == 200


@pytest.mark.parametrize("missing", ["refresh-token", "sheets-scope"])
def test_new_connection_requires_refresh_token_and_granted_sheets_scope(
    auth_app, google_token_request, verify_token, missing
):
    with auth_app.test_client() as client:
        _sign_in(client)
        payload = json.loads(google_token_request.return_value.text)
        if missing == "refresh-token":
            del payload["refresh_token"]
        else:
            payload["scope"] = "openid"
        google_token_request.return_value.text = json.dumps(payload)
        state = _start_connection(client)["state"][0]
        assert client.get(_callback_url(state)).status_code == 403
        assert GoogleSheetsConnection.query.count() == 0
        assert auth_manager.is_authenticated()


@pytest.mark.parametrize("path", ["/api/cards/Words", "/review/start/Words"])
def test_sheets_outage_returns_retryable_failure_and_preserves_login(
    auth_app, google_token_request, verify_token, path
):
    from app.services.google_credentials import GoogleCredentialsUnavailableError

    client = auth_app.test_client()
    _sign_in(client)
    _connect(client)
    with auth_app.app_context():
        User.query.one().add_spreadsheet("synthetic-sheet")

    with patch(
        "app.gsheet._get_credentials",
        side_effect=GoogleCredentialsUnavailableError("provider-details"),
    ):
        response = client.get(path)
        assert response.status_code == 503
        assert b"provider-details" not in response.data
        if path.startswith("/api/"):
            assert response.get_json()["code"] == "google_sheets_unavailable"
        assert client.get("/api/verbs/tenses").status_code == 200
    with auth_app.app_context():
        assert GoogleSheetsConnection.query.count() == 1


def test_expired_and_parallel_oauth_transactions(
    auth_app, google_token_request, verify_token, monkeypatch
):
    clock = Mock(return_value=1_700_000_000)
    monkeypatch.setattr("app.services.auth_manager.time", clock)
    with auth_app.test_client() as client:
        _sign_in(client)
        connect_state = _start_connection(client)["state"][0]
        login_state = _start_login(client)["state"][0]
        assert client.get(_callback_url(login_state)).location == "/"
        assert connect_state in sm.get(sk.AUTH_TRANSACTIONS)
        assert client.get(_callback_url(connect_state)).location == "/"
        assert auth_manager.user.google_sheets_connection is not None
        expired_state = _start_connection(client)["state"][0]
        clock.return_value += 600
        assert client.get(_callback_url(expired_state)).status_code == 400
        assert auth_manager.is_authenticated()


def test_connection_attempt_cannot_follow_browser_account_change(
    auth_app, google_token_request, verify_token
):
    with auth_app.test_client() as client:
        _sign_in(client)
        connect_state = _start_connection(client)["state"][0]
        verify_token.return_value = {"sub": "different-user"}
        _sign_in(client)
        before = google_token_request.call_count
        assert client.get(_callback_url(connect_state)).status_code == 400
        assert google_token_request.call_count == before
        assert auth_manager.user.google_user_id == "different-user"
        assert GoogleSheetsConnection.query.count() == 0


@pytest.mark.parametrize(
    ("method", "path", "is_json"),
    [
        ("GET", "/api/cards/Words", True),
        ("POST", "/validate-spreadsheet", True),
        ("POST", "/learn/start/Words", False),
        ("GET", "/review/start/Words", False),
    ],
)
def test_sheets_routes_report_connection_required_without_google_calls(
    auth_app, google_token_request, verify_token, method, path, is_json
):
    client = auth_app.test_client()
    _sign_in(client)
    with auth_app.app_context():
        User.query.one().add_spreadsheet("synthetic-sheet")
    google_token_request.reset_mock()
    with patch.object(Credentials, "refresh") as refresh:
        response = client.open(
            path, method=method, json={"spreadsheet_url": "synthetic-sheet"} if is_json else None
        )
        assert response.status_code == 403
        if is_json:
            assert response.get_json()["code"] == "google_sheets_connection_required"
        else:
            assert b"Connect Google Sheets" in response.data
        assert client.get("/api/verbs/tenses").status_code == 200
        refresh.assert_not_called()
    google_token_request.assert_not_called()
