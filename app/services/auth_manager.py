"""Manage browser sign-in, login sessions, and Google Sheets connection callbacks."""

import logging
from functools import wraps
from time import time
from urllib.parse import parse_qs, urlsplit

from flask import current_app, jsonify, redirect, request, url_for

from app.database import User, db
from app.services.google_credentials import (
    GoogleCredentialsService,
)
from app.services.google_oauth import GoogleOAuthPurpose, GoogleOAuthService, GoogleOAuthTransaction
from app.services.users import invalidate_user_sessions, login_or_create_user
from app.session_manager import SessionKeys as sk
from app.session_manager import SessionManager as sm

logger = logging.getLogger(__name__)

_LOGIN_LIFETIME_SECONDS = 7 * 24 * 60 * 60


class AuthManager:
    """Coordinate browser login, route protection, and logout."""

    @property
    def _google_oauth(self) -> GoogleOAuthService:
        return current_app.extensions["google_oauth"]

    @property
    def _google_credentials(self) -> GoogleCredentialsService:
        return current_app.extensions["google_credentials"]

    # OAuth Flow Methods

    def initiate_login(self, redirect_uri: str) -> str:
        """Start Google login and store the pending transaction in the browser session."""
        url, transaction = self._google_oauth.start_login(
            redirect_uri, expires_at=int(time()) + 600
        )
        self._store_transaction(transaction)
        return url

    def initiate_connection(self, redirect_uri: str) -> str:
        """Bind a Sheets consent attempt to the signed-in local user."""
        user = self.user
        if user is None:
            raise ValueError("Sign in before connecting Google Sheets")
        url, transaction = self._google_oauth.start_connection(
            redirect_uri,
            expires_at=int(time()) + 600,
            user_id=user.id,
            session_version=user.session_version,
            login_hint=user.email or "",
        )
        self._store_transaction(transaction)
        return url

    def _pending_transactions(self) -> dict:
        return {
            state: value
            for state, value in sm.get(sk.AUTH_TRANSACTIONS, {}).items()
            if value.get("expires_at", 0) > time()
        }

    def _store_transaction(self, transaction: GoogleOAuthTransaction) -> None:
        pending = self._pending_transactions()
        # Keep the transaction collection bounded while allowing parallel browser tabs.
        pending = dict(list(pending.items())[-7:])
        pending[transaction.state] = transaction.model_dump(mode="json")
        sm.set(sk.AUTH_TRANSACTIONS, pending)

    def handle_callback(self, authorization_response: str) -> GoogleOAuthPurpose:
        """Consume one OAuth transaction and complete its sign-in or connection action."""
        states = parse_qs(urlsplit(authorization_response).query, keep_blank_values=True).get(
            "state", []
        )
        if len(states) != 1 or not states[0]:
            raise ValueError("Google callback must include one state")
        pending = self._pending_transactions()
        value = pending.pop(states[0], None)
        sm.set(sk.AUTH_TRANSACTIONS, pending)
        if value is None:
            raise ValueError("Google authorization expired. Start again")
        transaction = GoogleOAuthTransaction.model_validate(value)

        if transaction.purpose == GoogleOAuthPurpose.CONNECT_SHEETS:
            user = self.user
            if (
                user is None
                or user.id != transaction.user_id
                or user.session_version != transaction.session_version
            ):
                raise ValueError("Sign in to the initiating account before connecting Sheets")

        identity, credentials = self._google_oauth.complete_authorization(
            authorization_response, transaction
        )
        if transaction.purpose == GoogleOAuthPurpose.CONNECT_SHEETS:
            if identity.google_user_id != user.google_user_id:
                raise ValueError("Choose the Google account used to sign in")
            self._google_credentials.save_connection(user, credentials)
            return transaction.purpose

        user = login_or_create_user(identity)
        sm.clear()
        sm.set(sk.AUTH_TRANSACTIONS, pending)
        sm.set(sk.USER_ID, user.id)
        sm.set(sk.USER_GOOGLE_ID, user.google_user_id)
        sm.set(sk.LOGIN_EXPIRES_AT, int(time()) + _LOGIN_LIFETIME_SECONDS)
        sm.set(sk.SESSION_VERSION, user.session_version)
        sm.regenerate_id()
        return transaction.purpose

    @property
    def user(self) -> User | None:
        """Return the local user for a current, unexpired browser login."""
        user_id = sm.get(sk.USER_ID)
        if user_id is None:
            return None

        expires_at = sm.get(sk.LOGIN_EXPIRES_AT)
        if isinstance(expires_at, int) and time() < expires_at:
            user = db.session.get(User, user_id)
            if (
                user is not None
                and user.session_version == sm.get(sk.SESSION_VERSION)
                and user.google_user_id == sm.get(sk.USER_GOOGLE_ID)
            ):
                return user

        sm.clear()
        return None

    def is_authenticated(self) -> bool:
        """Check the LangTut session and the current local user."""
        return self.user is not None

    def require_auth(self, f):
        """Redirect unauthenticated browser requests to Google sign-in."""

        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not self.is_authenticated():
                logger.info("Unauthenticated access to %s", request.path)
                return redirect(url_for("auth.auth"))
            return f(*args, **kwargs)

        return decorated_function

    def require_auth_api(self, f):
        """Return a JSON 401 for unauthenticated API requests."""

        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not self.is_authenticated():
                logger.info("Unauthenticated API access to %s", request.path)
                return jsonify({"error": "Unauthorized", "success": False}), 401
            return f(*args, **kwargs)

        return decorated_function

    def logout(self, *, logout_all_devices: bool = False) -> None:
        """End this login and optionally invalidate the user's other browser sessions."""
        if logout_all_devices and (user := self.user) is not None:
            invalidate_user_sessions(user)
        sm.clear()

    def disconnect_google_sheets(self) -> None:
        """Remove the signed-in user's Sheets connection."""
        if (user := self.user) is not None:
            self._google_credentials.disconnect(user.id)


# Create singleton instance
auth_manager = AuthManager()
