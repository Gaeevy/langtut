"""
Utility functions for the application.

This module provides general purpose utilities for the application.
"""

import json
from datetime import datetime

from src.config import CLIENT_SECRETS_FILE


def load_redirect_uris():
    """
    Load registered redirect URIs from client_secret.json file.

    Returns:
        List of registered redirect URIs or empty list if not found
    """
    try:
        with open(CLIENT_SECRETS_FILE) as f:
            client_secret_data = json.load(f)
            uris = client_secret_data.get('web', {}).get('redirect_uris', [])
            print(f'Registered redirect URIs: {uris}')
            return uris
    except Exception as e:
        print(f'Error loading redirect URIs from client_secret.json: {e}')
        return []


def get_timestamp():
    """
    Get current timestamp as datetime object.

    Returns:
        Current datetime object
    """
    return datetime.now()


def format_timestamp(dt):
    """
    Format a datetime object to string.

    Args:
        dt: Datetime object to format

    Returns:
        String representation of the datetime object
    """
    if isinstance(dt, str):
        return dt
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def parse_timestamp(timestamp_str):
    """
    Parse a timestamp string to datetime object.

    Args:
        timestamp_str: String timestamp in format '%Y-%m-%d %H:%M:%S'

    Returns:
        Datetime object or NEVER_SHOWN if parsing fails
    """
    from src.models import NEVER_SHOWN

    if not timestamp_str:
        return NEVER_SHOWN

    try:
        return datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
    except Exception:
        return NEVER_SHOWN


def ensure_utf8_encoding():
    """
    Ensure stdout and stderr are using UTF-8 encoding.
    """
    import sys

    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8')
