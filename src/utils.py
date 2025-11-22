"""
Utility functions for the application.

This module provides general purpose utilities for the application.
"""

import json
import logging
import tempfile
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


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


def load_credentials_from_env(env_json: str) -> str | None:
    """Load credentials from environment variable as JSON string and write to temporary file.

    Args:
        env_var_name: Name of environment variable containing JSON credentials

    Returns:
        Path to temporary credentials file, or None if not found
    """
    try:
        credentials_data = json.loads(env_json)
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as temp_file:
            json.dump(credentials_data, temp_file)
            return temp_file.name
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Error parsing {env_json}: {e}")
        return None


def load_credentials_from_file(file_path: str) -> str | None:
    """Load credentials from file path.

    Args:
        file_path: Path to credentials file

    Returns:
        Absolute path to credentials file, or None if not found
    """
    path = Path(file_path)
    if path.exists():
        logger.info(f"Loaded credentials from file: {file_path}")
        return str(path)

    logger.warning(f"Credentials file not found: {file_path}")
    return None


def resolve_secrets_file_path(env_variable: str | None, file_path: str | None) -> str | None:
    """Get OAuth client secrets file path.

    Priority:
    1. Secrets env var (JSON string)
    2. Secrets file path from settings
    """
    if not env_variable and not file_path:
        raise ValueError("Either secrets json string or secrets file must be set")
    if env_variable:
        return load_credentials_from_env(env_variable)
    return load_credentials_from_file(file_path)
