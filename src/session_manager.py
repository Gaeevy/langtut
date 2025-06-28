"""
Session management for Flask application.

Centralizes all session operations through a clean interface with enumerated keys
to prevent typos and enable refactoring-safe session access.
"""

from enum import Enum
from typing import Any

from flask import session


class SessionKeys(Enum):
    """Enumerated session keys with prefix namespacing for organization."""

    # Auth namespace - OAuth and authentication state
    AUTH_STATE = 'auth.state'
    AUTH_REDIRECT_URI = 'auth.redirect_uri'
    AUTH_CREDENTIALS = 'auth.credentials'

    # User namespace - User identification and metadata
    USER_ID = 'user.id'
    USER_GOOGLE_ID = 'user.google_id'

    # Learning namespace - Flashcard session state
    LEARNING_CARDS = 'learning.cards'
    LEARNING_CURRENT_INDEX = 'learning.current_index'
    LEARNING_ANSWERS = 'learning.answers'
    LEARNING_INCORRECT_CARDS = 'learning.incorrect_cards'
    LEARNING_REVIEWING_INCORRECT = 'learning.reviewing_incorrect'
    LEARNING_ACTIVE_TAB = 'learning.active_tab'
    LEARNING_ORIGINAL_COUNT = 'learning.original_count'
    LEARNING_SHEET_GID = 'learning.sheet_gid'
    LEARNING_LAST_LEVEL_CHANGE = 'learning.last_level_change'

    # Test namespace - Development and debugging
    TEST_SESSION = 'test.session'


class SessionManager:
    """
    Centralized session management with static methods.

    Provides a clean interface for session operations while maintaining
    compatibility with Flask's session object.
    """

    @staticmethod
    def get(key: SessionKeys, default: Any = None) -> Any:
        """
        Get session value with optional default.

        Args:
            key: SessionKeys enum value
            default: Default value if key not found

        Returns:
            Session value or default
        """
        return session.get(key.value, default)

    @staticmethod
    def set(key: SessionKeys, value: Any) -> None:
        """
        Set session value.

        Args:
            key: SessionKeys enum value
            value: Value to store in session
        """
        session[key.value] = value

    @staticmethod
    def remove(key: SessionKeys) -> None:
        """
        Remove session key.

        Args:
            key: SessionKeys enum value to remove
        """
        session.pop(key.value, None)

    @staticmethod
    def has(key: SessionKeys) -> bool:
        """
        Check if session key exists.

        Args:
            key: SessionKeys enum value to check

        Returns:
            True if key exists in session
        """
        return key.value in session

    @staticmethod
    def clear_namespace(namespace: str) -> None:
        """
        Clear all session keys with the given namespace prefix.

        Args:
            namespace: Namespace prefix (e.g., 'auth', 'learning')
        """
        keys_to_remove = [key for key in session if key.startswith(f'{namespace}.')]
        for key in keys_to_remove:
            session.pop(key, None)
