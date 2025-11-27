"""Centralized authentication manager for Google OAuth2.

This module provides the AuthManager class that handles the complete OAuth2
authentication lifecycle for the Language Learning Flashcard App.
"""

import json
import logging
from datetime import datetime, timedelta
from functools import wraps

from flask import redirect, request, url_for
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from src.config import Environment, config
from src.database import RefreshToken, User, db
from src.session_manager import SessionKeys as sk
from src.session_manager import SessionManager as sm

logger = logging.getLogger(__name__)


class AuthManager:
    """Centralized authentication manager for Google OAuth2.

    This class handles the complete OAuth2 authentication lifecycle including:
    - OAuth flow initiation and callback handling
    - Secure token storage (access tokens in session, refresh tokens in database)
    - Automatic token refresh with transparent error handling
    - Authentication state management
    - Route protection via decorator

    Architecture & Token Storage:
    -----------------------------
    Access Tokens:
        - Stored in Flask session (unencrypted)
        - Lifetime: ~1 hour
        - Acceptable to store in session due to short lifetime
        - Automatically refreshed when expired

    Refresh Tokens:
        - Stored in database (RefreshToken table, ENCRYPTED with Fernet)
        - Lifetime: Indefinite (until user revokes or Google policy expires)
        - Used only to obtain new access tokens
        - Never exposed to client or stored in session

    User Identification:
        - google_user_id extracted from ID token during OAuth callback
        - Used to find/create User record in database
        - Session stores user_id for quick lookups

    Authentication Flow:
    --------------------
    Initial Login (No Session):
        1. User accesses protected route → Redirected to /auth
        2. initiate_login() creates OAuth flow → User authorizes in Google
        3. Google redirects to /oauth2callback with authorization code
        4. handle_callback() exchanges code for tokens:
           - Access token (short-lived)
           - Refresh token (long-lived)
           - ID token (contains google_user_id, email, name)
        5. Extract google_user_id from ID token
        6. Find or create User in database
        7. Store refresh token in database (ENCRYPTED)
        8. Store access token + expiry in session
        9. Store user_id in session
        10. User is authenticated

    Returning User (Has Session):
        1. User accesses protected route → @require_auth checks session
        2. get_credentials() called:
           a. Check if access token in session is valid
           b. If valid → Return credentials immediately
           c. If expired → _refresh_credentials() is called
        3. _refresh_credentials():
           a. Get encrypted refresh token from database
           b. Decrypt refresh token
           c. Use refresh token to get new access token from Google
           d. Check if Google rotated refresh token (may happen)
           e. If rotated → Update database with new refresh token
           f. Store new access token in session
           g. Update last_used timestamp in database
        4. Return valid credentials → User continues seamlessly

    Session Expired:
        1. No session data available
        2. User redirected to login (full OAuth flow)
        3. Security feature: Don't auto-restore from database

    Token Rotation:
    ---------------
    Refresh tokens are rotated in two scenarios:

    1. Re-authentication (Full OAuth Flow):
       - User goes through complete OAuth flow
       - Google issues new refresh token
       - Stored in database (replaces or adds to existing tokens)

    2. Access Token Refresh (Google-Initiated):
       - During automatic access token refresh
       - Google MAY issue new refresh token (not guaranteed)
       - We check and update database if provided
       - Old token remains valid until Google revokes it

    Security Features:
    ------------------
    - Refresh tokens encrypted at rest using Fernet symmetric encryption
    - Encryption key stored in .secrets.toml (never in code)
    - Access tokens only in session (ephemeral, short-lived)
    - Automatic token refresh with 5-minute buffer before expiry
    - Failed refresh → Clear session and redirect to login
    - No silent failures - always clear error handling
    - Session expiry requires re-authentication (no DB restoration)
    - Multiple refresh tokens per user supported (different devices)

    Thread Safety:
    --------------
    - Uses Flask session (thread-local by default)
    - Database operations use SQLAlchemy (handles connection pooling)
    - No shared mutable state in class

    Usage Examples:
    ---------------
    Route Protection:
        @flashcard_bp.route('/learn')
        @auth_manager.require_auth
        def learn():
            user = auth_manager.get_current_user()
            return render_template('card.html', user=user)

    Service Layer:
        def read_spreadsheet():
            creds = auth_manager.get_credentials()  # Auto-refreshes
            if not creds:
                raise AuthenticationError("Not authenticated")
            gc = gspread.authorize(creds)
            return gc.open_by_key(spreadsheet_id)

    Manual Auth Check:
        if auth_manager.is_authenticated():
            # User is authenticated with valid credentials
            pass

    Logout:
        auth_manager.logout()  # Clears session + removes refresh tokens

    Error Handling:
    ---------------
    - OAuth errors: Redirect to error page with message
    - Refresh failures: Clear session and redirect to login
    - Database errors: Log and treat as not authenticated
    - Decryption errors: Remove corrupted token and redirect to login

    Dependencies:
    -------------
    - google.oauth2.credentials (Credentials object)
    - google_auth_oauthlib.flow (OAuth flow)
    - src.database (User, RefreshToken models)
    - src.session_manager (SessionManager, SessionKeys)
    - src.utils (encrypt_token, decrypt_token)
    - src.config (OAuth configuration)

    Notes:
    ------
    - Google refresh tokens don't expire unless:
      * User revokes access
      * User changes password
      * 6 months of inactivity (Google policy)
      * Manually revoked by us
    - Access tokens expire after ~1 hour (Google default)
    - ID tokens are only used during OAuth callback (not stored)
    - Multiple refresh tokens per user allow multi-device sessions
    """

    # OAuth token refresh buffer - refresh 5 minutes before expiry
    TOKEN_REFRESH_BUFFER = timedelta(minutes=5)

    def __init__(self):
        """Initialize AuthManager and load OAuth client configuration."""
        # Load client secrets from file
        with open(config.client_secrets_file_path) as f:
            secrets = json.load(f)
            # Handle both "web" and "installed" app types
            client_config = secrets.get("web") or secrets.get("installed")

            # Store as instance attributes for easy access
            self.client_id = client_config["client_id"]
            self.client_secret = client_config["client_secret"]
            self.token_uri = client_config.get("token_uri", "https://oauth2.googleapis.com/token")

    # OAuth Flow Methods

    def initiate_login(self, host: str) -> str:
        """Initiate OAuth flow and return authorization URL.

        Args:
            host: Request host (e.g., 'localhost:8080' or 'app.railway.app')

        Returns:
            Authorization URL to redirect user to
        """
        try:
            redirect_uri = self._get_redirect_uri(host)
            flow = self._create_flow(redirect_uri)

            authorization_url, state = flow.authorization_url(
                access_type="offline",  # Request refresh token
                include_granted_scopes="true",
            )

            # Store state and redirect_uri in session for verification
            sm.set(sk.AUTH_STATE, state)
            sm.set(sk.AUTH_REDIRECT_URI, redirect_uri)

            logger.info(f"OAuth flow initiated for host: {host}")
            return authorization_url

        except Exception as e:
            logger.error(f"Error initiating OAuth flow: {e}", exc_info=True)
            raise

    def handle_callback(self, authorization_response: str, host: str) -> User:
        """Handle OAuth callback and create/login user.

        Orchestrates the OAuth callback process by:
        1. Exchanging authorization code for tokens
        2. Extracting user info from ID token
        3. Creating or logging in user
        4. Storing tokens in appropriate locations

        Args:
            authorization_response: Full authorization response URL from Google
            host: Request host

        Returns:
            User object for the authenticated user

        Raises:
            Exception: If OAuth callback fails or user creation fails
        """
        try:
            # Step 1: Exchange code for tokens
            credentials = self._exchange_code_for_tokens(authorization_response, host)

            # Step 2: Extract user info from ID token
            user_info = self._extract_user_info_from_id_token(credentials.id_token)

            # Step 3: Login or create user
            user = self._login_or_create_user(user_info)

            # Step 4: Store tokens
            if credentials.refresh_token:
                refresh_token_id = self._save_refresh_token(user.id, credentials.refresh_token)
                sm.set(sk.REFRESH_TOKEN_ID, refresh_token_id)  # Track which token THIS session uses
                logger.info(
                    f"Refresh token stored for user {user.id} (token_id: {refresh_token_id})"
                )
            else:
                # Check if user already has a refresh token in database
                existing_token = RefreshToken.query.filter_by(user_id=user.id).first()
                if existing_token:
                    logger.info(
                        f"No new refresh token from Google, but user {user.id} has existing token in database"
                    )
                else:
                    logger.warning(
                        f"No refresh token received from Google and no existing token for user {user.id}. "
                        "User will need to re-authenticate when access token expires."
                    )

            sm.set(sk.ACCESS_TOKEN, credentials.token)
            sm.set(sk.ACCESS_TOKEN_EXPIRY, credentials.expiry)
            sm.set(sk.USER_ID, user.id)
            sm.set(sk.USER_GOOGLE_ID, user.google_user_id)

            # Clean up OAuth state
            sm.remove(sk.AUTH_STATE)
            sm.remove(sk.AUTH_REDIRECT_URI)

            return user

        except Exception as e:
            logger.error(f"Error handling OAuth callback: {e}", exc_info=True)
            raise

    def _exchange_code_for_tokens(self, authorization_response: str, host: str) -> Credentials:
        """Exchange authorization code for OAuth tokens.

        Args:
            authorization_response: Full authorization response URL from Google
            host: Request host

        Returns:
            Credentials object with access token, refresh token, and ID token
        """
        state = sm.get(sk.AUTH_STATE)
        redirect_uri = sm.get(sk.AUTH_REDIRECT_URI) or self._get_redirect_uri(host)

        flow = self._create_flow(redirect_uri, state)
        flow.fetch_token(authorization_response=authorization_response)

        return flow.credentials

    def _extract_user_info_from_id_token(self, id_token_jwt: str) -> dict[str, str]:
        """Extract user information from ID token.

        Args:
            id_token_jwt: JWT ID token from Google

        Returns:
            Dictionary with google_user_id, email, and name
        """
        id_info = id_token.verify_oauth2_token(id_token_jwt, Request(), self.client_id)

        user_info = {
            "google_user_id": id_info["sub"],
            "email": id_info.get("email", ""),
            "name": id_info.get("name", ""),
        }

        logger.info(f"OAuth callback successful for user: {user_info['email']}")
        return user_info

    def _login_or_create_user(self, user_info: dict[str, str]) -> User:
        """Login existing user or create new user.

        Args:
            user_info: Dictionary with google_user_id, email, and name

        Returns:
            User object
        """
        google_user_id = user_info["google_user_id"]
        email = user_info["email"]
        name = user_info["name"]

        user = User.query.filter_by(google_user_id=google_user_id).first()

        if not user:
            # Create new user
            user = User(google_user_id=google_user_id, email=email, name=name)
            db.session.add(user)
            db.session.commit()
            logger.info(f"New user created: {email} (ID: {user.id})")
        else:
            # Update existing user
            user.last_login = datetime.utcnow()
            if email and user.email != email:
                user.email = email
            if name and user.name != name:
                user.name = name
            db.session.commit()
            logger.info(f"User logged in: {email} (ID: {user.id})")

        return user

    def _create_flow(self, redirect_uri: str, state: str | None = None) -> Flow:
        """Create OAuth flow instance.

        Args:
            redirect_uri: OAuth callback redirect URI
            state: Optional state parameter for verification

        Returns:
            Configured Flow instance
        """
        flow_kwargs = {
            "client_secrets_file": config.client_secrets_file_path,
            "scopes": config.scopes,
            "redirect_uri": redirect_uri,
        }

        if state:
            flow_kwargs["state"] = state

        return Flow.from_client_secrets_file(**flow_kwargs)

    def _get_redirect_uri(self, host: str) -> str:
        """Get redirect URI based on environment.

        Args:
            host: Request host (e.g., 'localhost:8080' or 'app.railway.app')

        Returns:
            Redirect URI for OAuth callback
        """
        if config.environment == Environment.PRODUCTION:
            return f"https://{host}/oauth2callback"
        return f"http://{host}/oauth2callback"

    # Credential Management Methods

    def get_credentials(self) -> Credentials | None:
        """Get valid credentials, refreshing if needed.

        This is a PASSIVE GETTER - it returns credentials or None without
        enforcing authentication. It does NOT redirect to login or raise errors.

        Responsibility: Data retrieval (no policy enforcement)

        Flow:
        1. Check if user is logged in (user_id in session)
        2. Check if access token needs refresh
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

        Note:
            Returns None if:
            - User not logged in (no user_id in session)
            - Access token expired and refresh failed
            - No refresh token in database
        """
        creds = None

        # Check if user is logged in
        user_id = sm.get(sk.USER_ID)
        if not user_id:
            logger.debug("No user_id in session")
            return None

        # Check if token needs refresh
        if self._needs_token_refresh():
            logger.info("Access token expired or missing, attempting refresh")
            self._refresh_credentials(user_id)

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

        return datetime.utcnow() >= expiry - self.TOKEN_REFRESH_BUFFER

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
                refresh_token_obj = RefreshToken.query.get(refresh_token_id)
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
                token_uri=self.token_uri,
                client_id=self.client_id,
                client_secret=self.client_secret,
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
        try:
            refresh_token_obj = RefreshToken(user_id=user_id)
            refresh_token_obj.encrypt_and_store(token)
            db.session.add(refresh_token_obj)
            db.session.commit()
            logger.info(f"Refresh token saved for user {user_id} (ID: {refresh_token_obj.id})")
            return refresh_token_obj.id

        except Exception as e:
            logger.error(f"Failed to save refresh token for user {user_id}: {e}", exc_info=True)
            raise

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

        # Create credentials without refresh token (we keep that in DB only)
        return Credentials(
            token=access_token,
            refresh_token=None,  # Don't include refresh token
            token_uri=self.token_uri,
            client_id=self.client_id,
            client_secret=self.client_secret,
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
            return User.query.get(user_id)
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
                    token = RefreshToken.query.get(refresh_token_id)
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
