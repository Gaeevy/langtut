"""Refresh and cache Google access tokens for trusted local user IDs."""

import logging
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock

from cryptography.fernet import InvalidToken
from google.auth.exceptions import RefreshError, TransportError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from sqlalchemy.exc import SQLAlchemyError

from app.database import GoogleSheetsConnection, User, db

logger = logging.getLogger(__name__)

_REFRESH_BUFFER = timedelta(minutes=10)
_SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"


class GoogleConnectionRequiredError(RuntimeError):
    """The user has no grant or Google has confirmed that the grant is invalid."""


class GoogleCredentialsUnavailableError(RuntimeError):
    """Credentials could not be obtained. The stored grant may still be valid."""


@dataclass(frozen=True, repr=False)
class _AccessToken:
    """An access token and its expiry in naive UTC, as expected by google-auth."""

    token: str
    expiry: datetime

    @classmethod
    def from_credentials(cls, credentials: Credentials) -> "_AccessToken | None":
        expiry = credentials.expiry
        if not credentials.token or expiry is None:
            return None
        if expiry.tzinfo is not None:
            expiry = expiry.astimezone(UTC).replace(tzinfo=None)
        return cls(credentials.token, expiry)

    def credentials(self) -> Credentials:
        """Return a fresh SDK object containing only the access token."""
        return Credentials(token=self.token, expiry=self.expiry)

    def needs_refresh(self) -> bool:
        return self.expiry <= datetime.now(UTC).replace(tzinfo=None) + _REFRESH_BUFFER


class GoogleCredentialsService:
    """Manage Google Sheets grants and an access-token cache for one process."""

    def __init__(
        self, *, client_id: str, client_secret: str, token_uri: str, cache_size: int = 128
    ) -> None:
        if cache_size < 1:
            raise ValueError("Google credential cache size must be positive")
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_uri = token_uri
        self._cache_size = cache_size
        self._cache: OrderedDict[tuple[int, str], _AccessToken] = OrderedDict()
        self._cache_lock = Lock()
        # A fixed set of locks keeps memory bounded as users come and go.
        self._user_locks = tuple(Lock() for _ in range(32))

    def get_credentials(self, user_id: int, *, force_refresh: bool = False) -> Credentials:
        """Return access credentials for the user's active Google Sheets grant.

        Raises:
            GoogleConnectionRequiredError: There is no usable Sheets grant.
            GoogleCredentialsUnavailableError: Refresh failed without a confirmed revocation.
        """
        with self._user_locks[user_id % len(self._user_locks)]:
            cached = None
            if force_refresh:
                self._evict(user_id)
            try:
                connection = self._find_connection(user_id)
                if connection is None:
                    self._evict(user_id)
                    raise GoogleConnectionRequiredError("Connect Google Sheets to continue")
                key = (user_id, connection.google_user_id)
                if not force_refresh:
                    cached = self._get_cached(key)
                    if cached is not None and not cached.needs_refresh():
                        return cached.credentials()

                try:
                    token = self._refresh(connection)
                except GoogleConnectionRequiredError:
                    cached = None
                    self._evict(user_id)
                    db.session.delete(connection)
                    db.session.commit()
                    raise
            except (GoogleCredentialsUnavailableError, SQLAlchemyError) as exc:
                if isinstance(exc, SQLAlchemyError):
                    db.session.rollback()
                logger.warning("Google credential refresh unavailable (%s)", type(exc).__name__)
                if cached is not None and (credentials := cached.credentials()).valid:
                    return credentials
                raise GoogleCredentialsUnavailableError(
                    "Google credentials are unavailable"
                ) from None

            self._cache_token(key, token)
            return token.credentials()

    def save_connection(self, user: User, credentials: Credentials) -> None:
        """Store the grant from a verified Google login and cache its access token."""
        scopes = credentials.granted_scopes
        if scopes is not None and _SHEETS_SCOPE not in scopes:
            return

        user_id = user.id
        with self._user_locks[user_id % len(self._user_locks)]:
            try:
                connection = self._find_connection(user_id)
                if credentials.refresh_token:
                    if connection is None:
                        connection = GoogleSheetsConnection(
                            user_id=user_id, google_user_id=user.google_user_id
                        )
                        db.session.add(connection)
                    connection.rotate_token(credentials.refresh_token)
                    connection.granted_scopes = list(scopes) if scopes is not None else None
                    db.session.commit()
                    self._evict(user_id)
                if connection is not None:
                    token = _AccessToken.from_credentials(credentials)
                    if token is not None and token.credentials().valid:
                        self._cache_token((user_id, user.google_user_id), token)
            except (SQLAlchemyError, ValueError):
                db.session.rollback()
                raise GoogleCredentialsUnavailableError(
                    "Could not store Google credentials"
                ) from None

    def disconnect(self, user_id: int) -> None:
        """Remove LangTut's local Sheets grant and invalidate its cached access token."""
        with self._user_locks[user_id % len(self._user_locks)]:
            try:
                GoogleSheetsConnection.query.filter_by(user_id=user_id).delete()
                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
                raise GoogleCredentialsUnavailableError(
                    "Could not disconnect Google Sheets"
                ) from None
            self._evict(user_id)

    @staticmethod
    def _find_connection(user_id: int) -> GoogleSheetsConnection | None:
        return (
            GoogleSheetsConnection.query.join(User, User.id == GoogleSheetsConnection.user_id)
            .filter(
                GoogleSheetsConnection.user_id == user_id,
                GoogleSheetsConnection.google_user_id == User.google_user_id,
            )
            .populate_existing()
            .one_or_none()
        )

    def _get_cached(self, key: tuple[int, str]) -> _AccessToken | None:
        with self._cache_lock:
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
            return cached

    def _cache_token(self, key: tuple[int, str], token: _AccessToken) -> None:
        with self._cache_lock:
            self._cache[key] = token
            self._cache.move_to_end(key)
            if len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)

    def _evict(self, user_id: int) -> None:
        with self._cache_lock:
            for key in list(self._cache):
                if key[0] == user_id:
                    del self._cache[key]

    def _refresh(self, connection: GoogleSheetsConnection) -> _AccessToken:
        try:
            refresh_token = connection.get_decrypted_token()
        except (InvalidToken, ValueError):
            raise GoogleCredentialsUnavailableError("Could not read stored Google grant") from None

        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri=self._token_uri,
            client_id=self._client_id,
            client_secret=self._client_secret,
        )
        try:
            credentials.refresh(Request())
        except RefreshError as exc:
            response = exc.args[1] if len(exc.args) > 1 else None
            if (
                not exc.retryable
                and isinstance(response, dict)
                and response.get("error") == "invalid_grant"
            ):
                logger.warning("Google credential refresh rejected the stored grant")
                raise GoogleConnectionRequiredError("Reconnect Google Sheets to continue") from None
            raise GoogleCredentialsUnavailableError(
                "Google could not refresh credentials"
            ) from None
        except (TransportError, ValueError, TypeError):
            raise GoogleCredentialsUnavailableError(
                "Google could not refresh credentials"
            ) from None

        if credentials.refresh_token and credentials.refresh_token != refresh_token:
            connection.rotate_token(credentials.refresh_token)
        else:
            connection.touch()
        db.session.commit()

        token = _AccessToken.from_credentials(credentials)
        if token is None or not token.credentials().valid:
            raise GoogleCredentialsUnavailableError("Google did not return a usable access token")
        return token
