"""Manage browser authentication and adapt Google credentials to the browser session."""

import logging
from functools import wraps

from flask import current_app, jsonify, redirect, request, url_for
from google.oauth2.credentials import Credentials

from app.database import User, db
from app.services.google_credentials import (
    GoogleAccessToken,
    GoogleConnectionRequiredError,
    GoogleCredentialsService,
    GoogleCredentialsUnavailableError,
)
from app.services.google_oauth import GoogleOAuthService, GoogleOAuthTransaction
from app.services.users import login_or_create_user
from app.session_manager import SessionKeys as sk
from app.session_manager import SessionManager as sm

logger = logging.getLogger(__name__)


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

        refresh_token_id = sm.get(sk.REFRESH_TOKEN_ID) if sm.get(sk.USER_ID) == user.id else None
        if credentials.refresh_token:
            refresh_token_id = self._google_credentials.save_refresh_token(
                user.id, credentials.refresh_token
            )

        sm.clear()
        if refresh_token_id:
            sm.set(sk.REFRESH_TOKEN_ID, refresh_token_id)
        sm.set(sk.ACCESS_TOKEN, credentials.token)
        sm.set(sk.ACCESS_TOKEN_EXPIRY, credentials.expiry)
        sm.set(sk.USER_ID, user.id)
        sm.set(sk.USER_GOOGLE_ID, user.google_user_id)
        sm.regenerate_id()
        return user

    # Credential Management Methods

    def get_credentials(self, *, force_refresh: bool = False) -> Credentials | None:
        """Adapt Google credential failures for existing website callers."""
        # Remove this browser adapter once Sheets callers pass the user ID directly.
        user_id = sm.get(sk.USER_ID)
        if not user_id:
            return None

        if force_refresh:
            sm.remove(sk.ACCESS_TOKEN)
            sm.remove(sk.ACCESS_TOKEN_EXPIRY)
        browser_token = GoogleAccessToken.from_values(
            sm.get(sk.ACCESS_TOKEN), sm.get(sk.ACCESS_TOKEN_EXPIRY)
        )
        try:
            credentials = self._google_credentials.get_credentials(
                user_id,
                force_refresh=force_refresh,
                preferred_record_id=sm.get(sk.REFRESH_TOKEN_ID),
                browser_token=browser_token,
            )
        except GoogleConnectionRequiredError:
            sm.remove(sk.ACCESS_TOKEN)
            sm.remove(sk.ACCESS_TOKEN_EXPIRY)
            return None
        except GoogleCredentialsUnavailableError:
            return None

        access_token = GoogleAccessToken.from_values(credentials.token, credentials.expiry)
        if access_token != browser_token:
            sm.set(sk.ACCESS_TOKEN, credentials.token)
            sm.set(sk.ACCESS_TOKEN_EXPIRY, credentials.expiry)
        return credentials

    # Authentication State Methods

    def is_authenticated(self) -> bool:
        """Check whether the browser has usable Google credentials, refreshing if needed."""
        credentials = self.get_credentials()
        return credentials is not None and credentials.valid

    def require_auth(self, f):
        """Decorator for route protection - enforces authentication.

        This is an ACTIVE ENFORCER - it redirects to login if user is not
        authenticated. This is WHERE re-login enforcement happens.

        Responsibility: Policy enforcement (has side effects - redirects)

        How it works:
        1. Checks if user is authenticated (calls is_authenticated())
        2. If authenticated → Calls the wrapped function normally
        3. If NOT authenticated → Redirects to /auth (login page)
        4. Transparently handles token refresh (via is_authenticated())

        This is the PRIMARY way to protect routes that render HTML.

        When to use:
        - ✅ HTML routes that need authentication
        - ✅ Routes that should redirect to login page
        - ❌ API routes (use manual check + JSON error instead)
        - ❌ Service layer functions (use get_credentials() instead)

        Usage Examples:
            # Protecting HTML routes (RECOMMENDED)
            @flashcard_bp.route('/learn')
            @auth_manager.require_auth
            def learn():
                # At this point, user is GUARANTEED to be authenticated
                user = auth_manager.get_current_user()  # Will never be None
                return render_template('card.html', user=user)

            # API routes - DON'T use this decorator (use manual check)
            @api_bp.route('/api/data')
            def api_data():
                if not auth_manager.is_authenticated():
                    return jsonify({"error": "Unauthorized"}), 401  # JSON, not redirect
                return jsonify({"data": "..."})

        Returns:
            Decorated function that enforces authentication before execution

        Side Effects:
            Redirects to login page if user is not authenticated
        """

        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not self.is_authenticated():
                logger.info(f"Unauthenticated access to {request.url}, redirecting to login")
                return redirect(url_for("auth.auth"))
            return f(*args, **kwargs)

        return decorated_function

    def require_auth_api(self, f):
        """Decorator for API route protection - enforces authentication with JSON response.

        This is an ACTIVE ENFORCER for API endpoints - returns JSON 401 if user is not
        authenticated instead of redirecting to login page.

        Responsibility: Policy enforcement for APIs (has side effects - returns JSON error)

        How it works:
        1. Checks if user is authenticated (calls is_authenticated())
        2. If authenticated → Calls the wrapped function normally
        3. If NOT authenticated → Returns JSON {"error": "Unauthorized", "success": False}, 401
        4. Transparently handles token refresh (via is_authenticated())

        This is the PRIMARY way to protect API routes that return JSON.

        When to use:
        - ✅ API routes that need authentication
        - ✅ Routes that should return JSON errors (not HTML redirects)
        - ❌ HTML routes (use @require_auth instead)

        Usage Examples:
            # Protecting API routes (RECOMMENDED)
            @api_bp.route('/api/data')
            @auth_manager.require_auth_api
            def api_data():
                # At this point, user is GUARANTEED to be authenticated
                user = auth_manager.user  # Will never be None
                return jsonify({"data": "...", "user": user.email})

        Returns:
            Decorated function that enforces authentication before execution

        Side Effects:
            Returns JSON 401 error if user is not authenticated
        """

        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not self.is_authenticated():
                logger.info(f"Unauthenticated API access to {request.url}, returning 401")
                return jsonify({"error": "Unauthorized", "success": False}), 401
            return f(*args, **kwargs)

        return decorated_function

    @property
    def user(self) -> User | None:
        """Get the current authenticated user from the session.

        This is a PASSIVE GETTER - returns User or None without enforcing
        authentication. It only checks session, does NOT verify credentials.

        Responsibility: User retrieval (no authentication check)

        Best Practice:
        - Use inside @require_auth protected routes (user guaranteed to exist)
        - Don't use this to check authentication (use is_authenticated() instead)

        Usage Examples:
            # Inside protected route (RECOMMENDED)
            @flashcard_bp.route('/learn')
            @auth_manager.require_auth
            def learn():
                user = auth_manager.user  # Clean and simple
                return render_template('card.html', user=user)

            # Checking auth + getting user (if you can't use decorator)
            if auth_manager.is_authenticated():
                user = auth_manager.user
                # Process user...

        Returns:
            User object if user_id in session, None otherwise

        Note:
            This does NOT verify credentials are valid - it only checks if
            user_id exists in session. For full auth check, use is_authenticated().
        """
        user_id = sm.get(sk.USER_ID)
        if user_id:
            return db.session.get(User, user_id)
        return None

    # Session Methods

    def clear_auth_session(self) -> None:
        """Clear authentication data from session.

        Clears auth namespace and user namespace, but preserves learning data.
        """
        sm.clear_namespace("auth")
        sm.clear_namespace("user")
        logger.info("Auth session cleared")

    def logout(self, logout_all_devices: bool = False) -> None:
        """Clear this browser session and delete its grant or all the user's grants."""
        user_id = sm.get(sk.USER_ID)
        refresh_token_id = sm.get(sk.REFRESH_TOKEN_ID)

        if user_id and (logout_all_devices or refresh_token_id):
            try:
                self._google_credentials.delete_refresh_tokens(
                    user_id, record_id=None if logout_all_devices else refresh_token_id
                )
            except GoogleCredentialsUnavailableError:
                logger.warning("Could not delete stored Google credentials during logout")

        self.clear_auth_session()
        sm.clear_namespace("learning")
        logger.info("User logged out")


# Create singleton instance
auth_manager = AuthManager()
