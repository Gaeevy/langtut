"""Manage browser authentication and adapt Google credentials to the browser session."""

import logging
from functools import wraps
from time import time

from flask import current_app, jsonify, redirect, request, url_for
from google.oauth2.credentials import Credentials

from app.database import User, db
from app.services.google_credentials import (
    GoogleConnectionRequiredError,
    GoogleCredentialsService,
    GoogleCredentialsUnavailableError,
)
from app.services.google_oauth import GoogleOAuthService, GoogleOAuthTransaction
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
        url, transaction = self._google_oauth.start_login(redirect_uri)
        sm.set(sk.AUTH_STATE, transaction.state)
        sm.set(sk.AUTH_REDIRECT_URI, transaction.redirect_uri)
        sm.set(sk.AUTH_CODE_VERIFIER, transaction.code_verifier)
        return url

    def handle_callback(self, authorization_response: str) -> User:
        """Consume the pending login and establish a fresh session for the verified user."""
        state = sm.pop(sk.AUTH_STATE)
        redirect_uri = sm.pop(sk.AUTH_REDIRECT_URI)
        code_verifier = sm.pop(sk.AUTH_CODE_VERIFIER)
        if not (state and redirect_uri and code_verifier):
            raise ValueError("Missing pending Google login")

        transaction = GoogleOAuthTransaction(state, redirect_uri, code_verifier)
        identity, credentials = self._google_oauth.complete_login(
            authorization_response, transaction
        )
        user = login_or_create_user(identity)

        try:
            self._google_credentials.save_connection(user, credentials)
        except GoogleCredentialsUnavailableError:
            logger.warning("Could not save Google Sheets connection during sign-in")

        sm.clear()
        sm.set(sk.USER_ID, user.id)
        sm.set(sk.USER_GOOGLE_ID, user.google_user_id)
        sm.set(sk.LOGIN_EXPIRES_AT, int(time()) + _LOGIN_LIFETIME_SECONDS)
        sm.set(sk.SESSION_VERSION, user.session_version)
        sm.regenerate_id()
        return user

    def get_credentials(self, *, force_refresh: bool = False) -> Credentials | None:
        """Adapt Google credential failures for existing website callers."""
        # Remove this browser adapter once Sheets callers pass the user ID directly.
        user = self.user
        if user is None:
            return None
        try:
            return self._google_credentials.get_credentials(user.id, force_refresh=force_refresh)
        except (GoogleConnectionRequiredError, GoogleCredentialsUnavailableError):
            return None

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
