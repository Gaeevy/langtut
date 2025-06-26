"""
Authentication utilities for Google OAuth.

This module provides functions for managing Google OAuth credentials
and session handling.
"""

from flask import session
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


def get_credentials():
    """
    Get valid credentials from session or through the OAuth flow.

    Returns:
        Credentials object if available, otherwise None
    """
    creds = None

    # Load credentials from session if available
    if 'credentials' in session:
        creds = Credentials(**session['credentials'])

    # Check if credentials are expired and refresh if needed
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        session['credentials'] = credentials_to_dict(creds)

    return creds


def credentials_to_dict(credentials):
    """
    Convert credentials object to dictionary for session storage.

    Args:
        credentials: Google OAuth credentials object

    Returns:
        Dictionary representation of credentials suitable for session storage
    """
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes,
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
        token=credentials_dict.get('token'),
        refresh_token=credentials_dict.get('refresh_token'),
        token_uri=credentials_dict.get('token_uri'),
        client_id=credentials_dict.get('client_id'),
        client_secret=credentials_dict.get('client_secret'),
        scopes=credentials_dict.get('scopes'),
    )
