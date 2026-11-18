"""Index routes for the Language Learning Flashcard App.

Handles the homepage and main navigation.
"""

import logging

from flask import Blueprint, render_template, request

from app.gsheet import read_all_card_sets
from app.services.auth_manager import auth_manager
from app.services.google_credentials import (
    GoogleConnectionRequiredError,
    GoogleCredentialsUnavailableError,
)
from app.session_manager import SessionKeys as sk
from app.session_manager import SessionManager as sm

logger = logging.getLogger(__name__)

# Create blueprint
index_bp = Blueprint("index", __name__)


@index_bp.route("/")
def home():
    """Homepage - shows login or flashcard selection."""
    logger.debug("Loading index page")
    logger.info(f"User agent: {request.headers.get('User-Agent', 'Unknown')}")

    # Check if session is working
    if not sm.has(sk.TEST_SESSION):
        sm.set(sk.TEST_SESSION, "Session is working")

    user = auth_manager.user
    if user is None:
        logger.info("User not authenticated, showing login screen")
        return render_template("login.html")

    user_spreadsheet_id = user.get_active_spreadsheet_id()
    sheets_connected = user.google_sheets_connection is not None
    if not user_spreadsheet_id or not sheets_connected:
        return render_template(
            "setup.html",
            is_authenticated=True,
            sheets_connected=sheets_connected,
            spreadsheets=user.get_all_spreadsheets(),
            spreadsheet_toolbar_setup_mode=True,
        )

    # Set target language in session
    user_spreadsheet = user.get_active_spreadsheet()

    if user_spreadsheet:
        language_settings = user_spreadsheet.get_language_settings()
        target_lang = language_settings.get("target", "pt")  # Default to pt

        sm.set(sk.TARGET_LANGUAGE, target_lang)

    # Normal app flow with user's spreadsheet
    try:
        card_sets = read_all_card_sets(user_spreadsheet_id, user_id=user.id)
        logger.info(f"Found {len(card_sets)} card sets in spreadsheet {user_spreadsheet_id}")
        for card_set in card_sets:
            logger.info(f"  - {card_set.name}: {card_set.card_count} cards")
    except (GoogleConnectionRequiredError, GoogleCredentialsUnavailableError):
        raise

    except Exception as e:
        logger.error(f"Error reading card sets from spreadsheet {user_spreadsheet_id}: {e}")
        card_sets = []

    spreadsheets = user.get_all_spreadsheets()

    return render_template(
        "index.html",
        is_authenticated=True,
        sheets_connected=user.google_sheets_connection is not None,
        tabs=card_sets,
        user_spreadsheet_id=user_spreadsheet_id,
        spreadsheets=spreadsheets,
        spreadsheet_toolbar_setup_mode=False,
    )
