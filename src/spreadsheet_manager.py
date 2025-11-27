"""
Spreadsheet management utilities for the Language Learning Flashcard App.

Handles user spreadsheet associations and active spreadsheet tracking.
"""

import logging

from src.database import add_user_spreadsheet, get_user_active_spreadsheet
from src.services.auth_manager import auth_manager

logger = logging.getLogger(__name__)


def get_user_spreadsheet_id(session_obj=None):
    """Get the user's active spreadsheet ID from database.

    Args:
        session_obj: Unused parameter (kept for backward compatibility)

    Returns:
        Spreadsheet ID string if user has an active spreadsheet, None otherwise
    """
    user = auth_manager.get_current_user()
    if not user:
        return None

    active_spreadsheet = get_user_active_spreadsheet(user.id)
    if active_spreadsheet:
        return active_spreadsheet.spreadsheet_id

    return None


def set_user_spreadsheet(spreadsheet_id, spreadsheet_url=None, spreadsheet_name=None):
    """Set a spreadsheet as active for the current user.

    Args:
        spreadsheet_id: Google Sheets spreadsheet ID
        spreadsheet_url: Optional spreadsheet URL
        spreadsheet_name: Optional spreadsheet name

    Returns:
        UserSpreadsheet object

    Raises:
        Exception: If user not logged in
    """
    user = auth_manager.get_current_user()
    if not user:
        raise Exception("User not logged in")

    # Add/update spreadsheet in database
    user_spreadsheet = add_user_spreadsheet(
        user_id=user.id,
        spreadsheet_id=spreadsheet_id,
        spreadsheet_url=spreadsheet_url,
        spreadsheet_name=spreadsheet_name,
        make_active=True,
    )

    logger.info(f"Set active spreadsheet {spreadsheet_id} for user {user.email}")
    return user_spreadsheet
