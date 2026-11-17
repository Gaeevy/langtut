"""Manage browser authentication and session-backed Google credentials."""

import logging
from datetime import UTC, datetime, timedelta
from functools import wraps

from flask import current_app, jsonify, redirect, request, url_for
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from app.database import RefreshToken, User, db
from app.services.google_oauth import GoogleOAuthService, GoogleOAuthTransaction
from app.services.users import login_or_create_user
from app.session_manager import SessionKeys as sk
from app.session_manager import SessionManager as sm

logger = logging.getLogger(__name__)


class AuthManager:
    """Coordinate browser login and manage session-backed Google credentials."""

    TOKEN_REFRESH_BUFFER = timedelta(minutes=10)

    @property
    def _google_oauth(self) -> GoogleOAuthService:
        return current_app.extensions["google_oauth"]

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
            refresh_token_id = self._save_refresh_token(user.id, credentials.refresh_token)

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
        """Get valid credentials, refreshing if needed.

        This is a PASSIVE GETTER - it returns credentials or None without
        enforcing authentication. It does NOT redirect to login or raise errors.

        Responsibility: Data retrieval (no policy enforcement)

        Flow:
        1. Check if user is logged in (user_id in session)
        2. Check if access token needs refresh (or honor a forced refresh)
        3. If needed, refresh using database refresh token
        4. Get credentials from session
        5. Return credentials or None

        Who should enforce re-login?
        - Routes: Use @require_auth decorator (redirects to login)
        - APIs: Manual check + return JSON error
        - Services: Get credentials, handle None appropriately

        Usage Examples:
            # Service layer (internal use)
            creds = auth_manager.get_credentials()
            if not creds:
                return None  # Handle gracefully

            # Don't use this for route protection - use @require_auth instead!

        Returns:
            Valid Credentials object if authenticated, None otherwise

        Args:
            force_refresh: Refresh even if the session access token has not reached
                the normal refresh window. Used for a single retry after a Google API
                rejects an apparently valid access token.

        Note:
            Returns None if:
            - User not logged in (no user_id in session)
            - Access token expired and refresh failed
            - No refresh token in database
        """
        # Check if user is logged in
        user_id = sm.get(sk.USER_ID)
        if not user_id:
            logger.debug("No user_id in session")
            return None

        current_creds = self._credentials_from_session()

        # Check if token needs refresh
        if force_refresh or self._needs_token_refresh():
            reason = "forced" if force_refresh else "expired, missing, or expiring soon"
            logger.info(f"Access token refresh requested ({reason})")
            if not self._refresh_credentials(user_id):
                if force_refresh or current_creds is None or not current_creds.valid:
                    logger.warning("No usable Google credentials after refresh failure")
                    return None

                # A proactive refresh can fail transiently while the current token
                # is still valid. Keep serving it and retry refresh on the next request.
                logger.warning("Token refresh failed; temporarily using current valid token")
                return current_creds

        # Get credentials from session
        creds = self._credentials_from_session()

        if creds:
            logger.debug("Returning valid credentials from session")
        else:
            logger.warning("No valid credentials available")

        return creds

    def _needs_token_refresh(self) -> bool:
        """Check if access token needs to be refreshed.

        Returns:
            True if token is missing or will expire soon, False otherwise
        """
        access_token = sm.get(sk.ACCESS_TOKEN)
        expiry = sm.get(sk.ACCESS_TOKEN_EXPIRY)

        # No token in session - need refresh
        if not access_token or not expiry:
            return True

        # Check if token expires soon (with buffer)
        if isinstance(expiry, str):
            expiry = datetime.fromisoformat(expiry)

        expiry_utc = expiry if expiry.tzinfo else expiry.replace(tzinfo=UTC)
        return datetime.now(UTC) >= expiry_utc - self.TOKEN_REFRESH_BUFFER

    def _refresh_credentials(self, user_id: int) -> bool:
        """Refresh access token using refresh token from database.

        Uses the specific refresh token for THIS session (tracked by token_id in session).
        Falls back to most recent token if session token_id is not found.

        Args:
            user_id: User ID to refresh credentials for

        Returns:
            True if refresh successful, False otherwise
        """
        try:
            # Try to get the specific refresh token for THIS session
            refresh_token_id = sm.get(sk.REFRESH_TOKEN_ID)
            if refresh_token_id:
                refresh_token_obj = db.session.get(RefreshToken, refresh_token_id)
                if refresh_token_obj and refresh_token_obj.user_id == user_id:
                    logger.debug(f"Using session-specific refresh token {refresh_token_id}")
                else:
                    logger.warning(
                        f"Session token {refresh_token_id} not found, falling back to most recent"
                    )
                    refresh_token_obj = None
            else:
                refresh_token_obj = None

            # Fallback: Get most recent refresh token if session token not found
            if not refresh_token_obj:
                refresh_token_obj = (
                    RefreshToken.query.filter_by(user_id=user_id)
                    .order_by(RefreshToken.last_used.desc())
                    .first()
                )
                if refresh_token_obj:
                    logger.debug(f"Using most recent refresh token {refresh_token_obj.id}")

            if not refresh_token_obj:
                logger.warning(f"No refresh token found for user {user_id}")
                return False

            # Decrypt refresh token
            refresh_token = refresh_token_obj.get_decrypted_token()

            # Create credentials object with refresh token
            credentials = Credentials(
                token=None,  # Will be refreshed
                refresh_token=refresh_token,
                token_uri=self._google_oauth.token_uri,
                client_id=self._google_oauth.client_id,
                client_secret=self._google_oauth.client_secret,
            )

            # Refresh the access token
            credentials.refresh(Request())

            logger.info(f"Access token refreshed for user {user_id}")

            # Check if Google rotated the refresh token
            if credentials.refresh_token and credentials.refresh_token != refresh_token:
                logger.info("Google rotated refresh token, updating database")
                refresh_token_obj.rotate_token(credentials.refresh_token)
            else:
                # Just update last_used
                refresh_token_obj.touch()

            db.session.commit()

            # Store new access token in session
            sm.set(sk.ACCESS_TOKEN, credentials.token)
            sm.set(sk.ACCESS_TOKEN_EXPIRY, credentials.expiry)

            return True

        except Exception as e:
            logger.error(f"Failed to refresh credentials for user {user_id}: {e}", exc_info=True)
            return False

    def _save_refresh_token(self, user_id: int, token: str) -> int:
        """Save refresh token to database (encrypted).

        Args:
            user_id: User ID to save token for
            token: Plain text refresh token from Google

        Returns:
            ID of the created RefreshToken record
        """
        refresh_token_obj = RefreshToken(user_id=user_id)
        refresh_token_obj.encrypt_and_store(token)
        db.session.add(refresh_token_obj)
        db.session.commit()
        logger.info(f"Refresh token saved for user {user_id} (ID: {refresh_token_obj.id})")
        return refresh_token_obj.id

    def _credentials_from_session(self) -> Credentials | None:
        """Create Credentials object from session data.

        Returns:
            Credentials object or None if session data incomplete
        """
        access_token = sm.get(sk.ACCESS_TOKEN)
        expiry = sm.get(sk.ACCESS_TOKEN_EXPIRY)

        if not access_token:
            return None

        if isinstance(expiry, str):
            expiry = datetime.fromisoformat(expiry)

        # google-auth compares expiry with a naive UTC clock internally. Flask
        # session serializers may preserve or restore the value as timezone-aware.
        if expiry and expiry.tzinfo:
            expiry = expiry.astimezone(UTC).replace(tzinfo=None)

        # Create credentials without refresh token (we keep that in DB only)
        return Credentials(
            token=access_token,
            refresh_token=None,  # Don't include refresh token
            token_uri=self._google_oauth.token_uri,
            client_id=self._google_oauth.client_id,
            client_secret=self._google_oauth.client_secret,
            expiry=expiry,
        )

    # Authentication State Methods

    def is_authenticated(self) -> bool:
        """Check if the current user is authenticated.

        This is a PASSIVE CHECKER - it returns True/False without enforcing
        authentication. It does NOT redirect to login or raise errors.

        Responsibility: State checking (no policy enforcement)

        How it works:
        1. Calls get_credentials() to get credentials (auto-refreshes if needed)
        2. Returns True if credentials exist and are valid
        3. Returns False otherwise (no side effects)

        Who should enforce re-login?
        - Routes: Use @require_auth decorator (not this method)
        - APIs: Use this method + return JSON error
        - Services: Use get_credentials() directly

        Usage Examples:
            # API endpoint (JSON response)
            @api_bp.route('/api/data')
            def api_data():
                if not auth_manager.is_authenticated():
                    return jsonify({"error": "Unauthorized"}), 401
                return jsonify({"data": "..."})

            # Don't use for route protection - use @require_auth decorator instead!

        Returns:
            True if user is authenticated with valid credentials, False otherwise

        Note:
            This method has NO side effects - it only checks state.
            For route protection, use @require_auth decorator.
        """
        # Try to get valid credentials (will auto-refresh if needed)
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
        """Logout user.

        By default, logs out only THIS session (single device).
        Optionally can log out ALL sessions/devices.

        Args:
            logout_all_devices: If True, delete ALL refresh tokens (logout everywhere).
                              If False (default), delete only THIS session's token.

        Multi-device behavior:
            - Default: Logs out THIS device only, other sessions remain active
            - logout_all_devices=True: Logs out from ALL devices/sessions
        """
        user_id = sm.get(sk.USER_ID)
        refresh_token_id = sm.get(sk.REFRESH_TOKEN_ID)

        if user_id:
            try:
                if logout_all_devices:
                    # Delete ALL refresh tokens for user (logout everywhere)
                    count = RefreshToken.query.filter_by(user_id=user_id).delete()
                    db.session.commit()
                    logger.info(f"All refresh tokens deleted for user {user_id} ({count} tokens)")
                elif refresh_token_id:
                    # Delete only THIS session's refresh token (single device logout)
                    token = db.session.get(RefreshToken, refresh_token_id)
                    if token and token.user_id == user_id:
                        db.session.delete(token)
                        db.session.commit()
                        logger.info(f"Refresh token {refresh_token_id} deleted for user {user_id}")
                    else:
                        logger.warning(f"Session token {refresh_token_id} not found for logout")
                else:
                    logger.warning(f"No refresh token ID in session for user {user_id}")
            except Exception as e:
                logger.error(f"Error deleting refresh tokens: {e}", exc_info=True)

        # Clear session
        self.clear_auth_session()
        sm.clear_namespace("learning")  # Also clear learning data on logout

        logger.info("User logged out")


# Create singleton instance
auth_manager = AuthManager()
