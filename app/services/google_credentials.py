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

from app.database import RefreshToken, db

logger = logging.getLogger(__name__)

_REFRESH_BUFFER = timedelta(minutes=10)


class GoogleConnectionRequiredError(RuntimeError):
    """The user has no grant or Google has confirmed that the grant is invalid."""


class GoogleCredentialsUnavailableError(RuntimeError):
    """Credentials could not be obtained. The stored grant may still be valid."""


@dataclass(frozen=True, repr=False)
class GoogleAccessToken:
    """An access token and its expiry in naive UTC, as expected by google-auth."""

    token: str
    expiry: datetime

    @classmethod
    def from_values(
        cls, token: str | None, expiry: datetime | str | None
    ) -> "GoogleAccessToken | None":
        if not token or not expiry:
            return None
        if isinstance(expiry, str):
            try:
                expiry = datetime.fromisoformat(expiry)
            except ValueError:
                return None
        if expiry.tzinfo is not None:
            expiry = expiry.astimezone(UTC).replace(tzinfo=None)
        return cls(token, expiry)

    def credentials(self) -> Credentials:
        """Return a fresh SDK object containing only the access token."""
        return Credentials(token=self.token, expiry=self.expiry)

    def needs_refresh(self) -> bool:
        return self.expiry <= datetime.now(UTC).replace(tzinfo=None) + _REFRESH_BUFFER


class GoogleCredentialsService:
    """Manage legacy Google grants and an access-token cache for one process."""

    def __init__(
        self, *, client_id: str, client_secret: str, token_uri: str, cache_size: int = 128
    ) -> None:
        if cache_size < 1:
            raise ValueError("Google credential cache size must be positive")
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_uri = token_uri
        self._cache_size = cache_size
        self._cache: OrderedDict[tuple[int, int], GoogleAccessToken] = OrderedDict()
        self._cache_lock = Lock()
        # A fixed set of locks keeps memory bounded as users come and go.
        self._user_locks = tuple(Lock() for _ in range(32))

    def get_credentials(
        self,
        user_id: int,
        *,
        force_refresh: bool = False,
        preferred_record_id: int | None = None,
        browser_token: GoogleAccessToken | None = None,
    ) -> Credentials:
        """Get access credentials in an application context, using an owned grant.

        The browser adapter may supply its existing token during the transition.
        It stays local to the caller and is never added to the shared cache.

        Raises:
            GoogleConnectionRequiredError: There is no usable Google grant.
            GoogleCredentialsUnavailableError: A provider or storage failure prevented refresh.
        """
        if not force_refresh and browser_token is not None and not browser_token.needs_refresh():
            return browser_token.credentials()

        with self._user_locks[user_id % len(self._user_locks)]:
            fallback = None if force_refresh else browser_token
            try:
                grant = self._find_grant(user_id, preferred_record_id)
                if grant is None:
                    if fallback is not None and (credentials := fallback.credentials()).valid:
                        return credentials
                    raise GoogleConnectionRequiredError("Connect Google Sheets to continue")

                key = (user_id, grant.id)
                if force_refresh:
                    self._invalidate(user_id, grant.id)
                else:
                    cached = self._get_cached(key)
                    if cached is not None:
                        if not cached.needs_refresh():
                            return cached.credentials()
                        if fallback is None or cached.expiry >= fallback.expiry:
                            fallback = cached

                token = self._refresh(grant)
            except GoogleConnectionRequiredError:
                self._invalidate(user_id, grant.id if grant is not None else None)
                raise
            except (GoogleCredentialsUnavailableError, SQLAlchemyError) as exc:
                if isinstance(exc, SQLAlchemyError):
                    db.session.rollback()
                    if force_refresh:
                        self._invalidate(user_id, None)
                logger.warning("Google credential refresh unavailable (%s)", type(exc).__name__)
                if fallback is not None and (credentials := fallback.credentials()).valid:
                    return credentials
                raise GoogleCredentialsUnavailableError(
                    "Google credentials are unavailable"
                ) from None

            with self._cache_lock:
                self._cache[key] = token
                self._cache.move_to_end(key)
                if len(self._cache) > self._cache_size:
                    self._cache.popitem(last=False)
            return token.credentials()

    def save_refresh_token(self, user_id: int, token: str) -> int:
        """Store a newly issued refresh token and return its legacy record ID."""
        try:
            grant = RefreshToken(user_id=user_id)
            grant.encrypt_and_store(token)
            db.session.add(grant)
            db.session.flush()
            record_id = grant.id
            db.session.commit()
        except (SQLAlchemyError, ValueError):
            db.session.rollback()
            raise GoogleCredentialsUnavailableError("Could not store Google credentials") from None
        return record_id

    def delete_refresh_tokens(self, user_id: int, *, record_id: int | None = None) -> None:
        """Delete the user's selected grant or all their grants and evict cached tokens."""
        with self._user_locks[user_id % len(self._user_locks)]:
            query = RefreshToken.query.filter_by(user_id=user_id)
            if record_id is not None:
                query = query.filter_by(id=record_id)
            try:
                query.delete()
                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
                raise GoogleCredentialsUnavailableError(
                    "Could not delete Google credentials"
                ) from None
            self._invalidate(user_id, record_id)

    @staticmethod
    def _find_grant(user_id: int, preferred_record_id: int | None) -> RefreshToken | None:
        grants = RefreshToken.query.filter_by(user_id=user_id).populate_existing()
        if preferred_record_id is not None:
            preferred = grants.filter_by(id=preferred_record_id).first()
            if preferred is not None:
                return preferred
        return grants.order_by(RefreshToken.last_used.desc(), RefreshToken.id.desc()).first()

    def _get_cached(self, key: tuple[int, int]) -> GoogleAccessToken | None:
        with self._cache_lock:
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
            return cached

    def _invalidate(self, user_id: int, record_id: int | None) -> None:
        with self._cache_lock:
            if record_id is not None:
                self._cache.pop((user_id, record_id), None)
                return
            for key in list(self._cache):
                if key[0] == user_id:
                    del self._cache[key]

    def _refresh(self, grant: RefreshToken) -> GoogleAccessToken:
        try:
            refresh_token = grant.get_decrypted_token()
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
            grant.rotate_token(credentials.refresh_token)
        else:
            grant.touch()
        db.session.commit()

        token = GoogleAccessToken.from_values(credentials.token, credentials.expiry)
        if token is None or not token.credentials().valid:
            raise GoogleCredentialsUnavailableError("Google did not return a usable access token")
        return token
