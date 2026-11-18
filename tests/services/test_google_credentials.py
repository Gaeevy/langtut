"""Exercise Google grant selection and refresh without a browser session."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs

import pytest
from cryptography.fernet import Fernet
from flask import Flask, has_request_context
from google.auth.exceptions import TransportError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from app.config import config
from app.database import GoogleSheetsConnection, User, db
from app.services.google_credentials import (
    GoogleConnectionRequiredError,
    GoogleCredentialsService,
    GoogleCredentialsUnavailableError,
)


@pytest.fixture
def credentials_app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "encryption_key", Fernet.generate_key().decode())
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path / 'credentials.sqlite'}"
    db.init_app(app)
    with app.app_context():
        db.create_all()
    return app


@pytest.fixture
def service(google_oauth):
    return GoogleCredentialsService(
        client_id=google_oauth.client_id,
        client_secret=google_oauth.client_secret,
        token_uri=google_oauth.token_uri,
        sheets_scopes=config.google_sheets_scopes,
        cache_size=2,
    )


def _add_google_user(service: GoogleCredentialsService, subject: str) -> int:
    user = User(google_user_id=subject, email=f"{subject}@example.test")
    db.session.add(user)
    db.session.flush()
    user_id = user.id
    service.save_connection(
        user,
        Credentials(
            token=None, refresh_token=f"grant-{subject}", scopes=config.google_sheets_scopes
        ),
    )
    return user_id


def _google_response(access_token: str, *, expires_in: int = 3600, **payload):
    return Mock(
        status=200,
        data=json.dumps(
            {"access_token": access_token, "expires_in": expires_in, **payload}
        ).encode(),
    )


@pytest.fixture
def send_to_google(monkeypatch):
    def send(*, body, **kwargs):
        grant = parse_qs(body.decode())["refresh_token"][0]
        return _google_response(f"access-for-{grant}")

    send_mock = Mock(side_effect=send)
    monkeypatch.setattr(Request, "__call__", send_mock)
    return send_mock


def test_refresh_without_request_context_isolates_users(credentials_app, service, send_to_google):
    with credentials_app.app_context():
        assert not has_request_context()
        alice_id = _add_google_user(service, "alice")
        bob_id = _add_google_user(service, "bob")

        alice_credentials = service.get_credentials(alice_id)
        bob_credentials = service.get_credentials(bob_id)

        assert alice_credentials.token == "access-for-grant-alice"
        assert bob_credentials.token == "access-for-grant-bob"
        assert alice_credentials.refresh_token is None
        assert alice_credentials.client_secret is None
        alice_credentials.token = "modified-by-caller"
        assert service.get_credentials(alice_id).token == "access-for-grant-alice"
        assert send_to_google.call_count == 2


def test_refresh_persists_rotation_before_reusing_grant(credentials_app, service, send_to_google):
    send_to_google.side_effect = [
        _google_response("first-access", refresh_token="rotated-grant"),
        _google_response("second-access"),
    ]
    with credentials_app.app_context():
        user_id = _add_google_user(service, "one")
        assert service.get_credentials(user_id).token == "first-access"
    with credentials_app.app_context():
        grant = db.session.get(GoogleSheetsConnection, user_id)
        assert grant.get_decrypted_token() == "rotated-grant"
        assert grant.token_encrypted != "rotated-grant"

        assert service.get_credentials(user_id, force_refresh=True).token == "second-access"
        assert parse_qs(send_to_google.call_args.kwargs["body"].decode())["refresh_token"] == [
            "rotated-grant"
        ]


def test_new_grant_replaces_old_connection_and_cache(credentials_app, service, send_to_google):
    with credentials_app.app_context():
        user_id = _add_google_user(service, "one")
        assert service.get_credentials(user_id).token == "access-for-grant-one"
        user = db.session.get(User, user_id)
        service.save_connection(
            user,
            Credentials(
                token=None,
                refresh_token="replacement-grant",
                granted_scopes=config.google_identity_scopes + config.google_sheets_scopes,
            ),
        )

        assert service.get_credentials(user_id).token == "access-for-replacement-grant"
        assert (
            GoogleSheetsConnection.query.one().granted_scopes
            == config.google_identity_scopes + config.google_sheets_scopes
        )
        assert send_to_google.call_count == 2


def test_login_without_new_refresh_token_preserves_existing_connection(
    credentials_app, service, send_to_google
):
    with credentials_app.app_context():
        user_id = _add_google_user(service, "one")
        user = db.session.get(User, user_id)
        service.save_connection(user, Credentials(token=None, scopes=config.google_sheets_scopes))

        assert service.get_credentials(user_id).token == "access-for-grant-one"
        send_to_google.assert_called_once()


def test_connection_with_wrong_google_subject_is_unusable(credentials_app, service, send_to_google):
    with credentials_app.app_context():
        user_id = _add_google_user(service, "one")
        assert service.get_credentials(user_id).token == "access-for-grant-one"
        connection = db.session.get(GoogleSheetsConnection, user_id)
        connection.google_user_id = "different-google-user"
        db.session.commit()

        with pytest.raises(GoogleConnectionRequiredError):
            service.get_credentials(user_id)
        send_to_google.assert_called_once()


def test_expiry_and_outage_fall_back_only_to_usable_access_token(
    credentials_app, service, send_to_google
):
    send_to_google.side_effect = [
        _google_response("expiring-access", expires_in=540),
        TransportError("synthetic provider error"),
        _google_response("renewed-access"),
    ]
    with credentials_app.app_context():
        user_id = _add_google_user(service, "one")
        assert service.get_credentials(user_id).token == "expiring-access"
        assert service.get_credentials(user_id).token == "expiring-access"
        assert service.get_credentials(user_id).token == "renewed-access"
        assert send_to_google.call_count == 3
        assert db.session.get(GoogleSheetsConnection, user_id).get_decrypted_token() == "grant-one"


def test_provider_outage_uses_only_the_sdk_retry_budget(
    credentials_app, service, send_to_google, monkeypatch
):
    monkeypatch.setattr("google.auth._exponential_backoff.time", SimpleNamespace(sleep=Mock()))
    send_to_google.side_effect = None
    send_to_google.return_value = Mock(status=503, data=b'{"error":"temporarily_unavailable"}')

    with credentials_app.app_context():
        user_id = _add_google_user(service, "one")
        with pytest.raises(GoogleCredentialsUnavailableError):
            service.get_credentials(user_id)

        assert send_to_google.call_count == 3
        assert db.session.get(GoogleSheetsConnection, user_id) is not None


def test_forced_refresh_evicts_rejected_token_even_if_refresh_fails(
    credentials_app, service, send_to_google
):
    send_to_google.side_effect = [
        _google_response("rejected-access"),
        TransportError("provider outage"),
        TransportError("provider outage"),
    ]
    with credentials_app.app_context():
        user_id = _add_google_user(service, "one")
        assert service.get_credentials(user_id).token == "rejected-access"

        with pytest.raises(GoogleCredentialsUnavailableError):
            service.get_credentials(user_id, force_refresh=True)
        assert send_to_google.call_count == 2

        with pytest.raises(GoogleCredentialsUnavailableError):
            service.get_credentials(user_id)
        assert send_to_google.call_count == 3


def test_invalid_grant_requires_reconnection_and_sanitizes_provider_details(
    credentials_app, service, send_to_google, caplog
):
    send_to_google.side_effect = [
        _google_response("expiring-access", expires_in=540),
        Mock(status=400, data=b'{"error":"invalid_grant","error_description":"provider-details"}'),
    ]
    with credentials_app.app_context():
        user_id = _add_google_user(service, "one")
        assert service.get_credentials(user_id).token == "expiring-access"

        with pytest.raises(GoogleConnectionRequiredError, match="Reconnect") as error:
            service.get_credentials(user_id)
        assert send_to_google.call_count == 2
        assert "provider-details" not in caplog.text
        assert error.value.__suppress_context__
        assert db.session.get(GoogleSheetsConnection, user_id) is None
        with pytest.raises(GoogleConnectionRequiredError):
            service.get_credentials(user_id)
        assert send_to_google.call_count == 2


def test_cache_is_bounded_and_grant_deletion_invalidates_access(
    credentials_app, service, send_to_google
):
    with credentials_app.app_context():
        user_ids = [_add_google_user(service, subject) for subject in ("one", "two", "three")]
        for user_id in user_ids:
            service.get_credentials(user_id)
        service.get_credentials(user_ids[-1])
        assert send_to_google.call_count == 3
        service.get_credentials(user_ids[0])
        assert send_to_google.call_count == 4

        service.disconnect(user_ids[0])
        with pytest.raises(GoogleConnectionRequiredError):
            service.get_credentials(user_ids[0])
        assert send_to_google.call_count == 4


def test_concurrent_requests_share_one_refresh(credentials_app, service, send_to_google):
    with credentials_app.app_context():
        user_id = _add_google_user(service, "one")

    first_refresh = Event()
    second_request = Event()

    def send(**kwargs):
        first_refresh.set()
        assert second_request.wait(5)
        return _google_response("shared-access")

    def get_credentials(started: Event | None = None):
        with credentials_app.app_context():
            if started is not None:
                started.set()
            return service.get_credentials(user_id).token

    send_to_google.side_effect = send
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(get_credentials)
        assert first_refresh.wait(5)
        second = pool.submit(get_credentials, second_request)
        assert first.result(timeout=5) == second.result(timeout=5) == "shared-access"
    send_to_google.assert_called_once()
