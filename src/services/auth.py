"""
Google OAuth2 authentication utilities.

Provides functions for managing Google OAuth2 credentials and OAuth flow.
"""

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from src.config import Environment, config
from src.session_manager import SessionKeys as sk
from src.session_manager import SessionManager as sm


def credentials_to_dict(credentials: Credentials) -> dict:
    """Convert Credentials to dict for session storage."""
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }


def get_redirect_uri(host: str) -> str:
    """Get redirect URI based on environment.

    Args:
        host: Request host (e.g., 'localhost:8080' or 'app.railway.app')

    Returns:
        Redirect URI for OAuth callback
    """
    if config.environment == Environment.PRODUCTION:
        return f"https://{host}/oauth2callback"
    return f"http://{host}/oauth2callback"


def create_oauth_flow(redirect_uri: str, state: str | None = None) -> Flow:
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


def get_credentials() -> Credentials | None:
    """Get OAuth2 credentials from session.

    Returns:
        Google Credentials object or None if not authenticated
    """
    if not sm.has(sk.AUTH_CREDENTIALS):
        return None

    creds = Credentials(**sm.get(sk.AUTH_CREDENTIALS))

    # Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        sm.set(sk.AUTH_CREDENTIALS, credentials_to_dict(creds))
        return creds

    # Return None if invalid
    if not creds or not creds.valid:
        return None

    return creds
