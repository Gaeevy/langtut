"""
Utility functions for the application.

This module provides general purpose utilities for the application.
"""

import json
from datetime import datetime

from src.config import config


def load_redirect_uris():
    """
    Load registered redirect URIs from client_secret.json file.

    Returns:
        list: List of registered redirect URIs
    """
    try:
        with open(config.client_secrets_file_path) as f:
            client_secrets = json.load(f)
            return client_secrets["web"]["redirect_uris"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
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
    return dt.strftime("%Y-%m-%d %H:%M:%S")


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
        return datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return NEVER_SHOWN


def ensure_utf8_encoding():
    """
    Ensure stdout and stderr are using UTF-8 encoding.
    """
    import sys

    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.stderr.encoding != "utf-8":
        sys.stderr.reconfigure(encoding="utf-8")
