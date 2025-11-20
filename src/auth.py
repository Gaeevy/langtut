"""
Google OAuth2 authentication utilities.

Provides functions for managing Google OAuth2 credentials and authentication state.
"""

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from src.session_manager import SessionKeys as sk
from src.session_manager import SessionManager as sm


def get_credentials():
    """Get OAuth2 credentials from session."""
    if not sm.has(sk.AUTH_CREDENTIALS):
        return None

    creds = Credentials(**sm.get(sk.AUTH_CREDENTIALS))

    # If there are no (valid) credentials available, return None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Save the refreshed credentials back to the session
            sm.set(sk.AUTH_CREDENTIALS, credentials_to_dict(creds))
        else:
            return None

    return creds


def credentials_to_dict(credentials):
    """Convert Credentials object to dictionary for session storage."""
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }


def dict_to_credentials(credentials_dict):
    """
    Convert dictionary back to credentials object.

    Args:
        credentials_dict: Dictionary representation of credentials

    Returns:
        Google OAuth credentials object
    """
    return Credentials(
        token=credentials_dict.get("token"),
        refresh_token=credentials_dict.get("refresh_token"),
        token_uri=credentials_dict.get("token_uri"),
        client_id=credentials_dict.get("client_id"),
        client_secret=credentials_dict.get("client_secret"),
        scopes=credentials_dict.get("scopes"),
    )
