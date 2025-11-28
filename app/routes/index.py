"""Index routes for the Language Learning Flashcard App.

Handles the homepage and main navigation.
"""

import logging

from flask import Blueprint, render_template, request

from app.gsheet import read_all_card_sets
from app.services.auth_manager import auth_manager
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

    # Check authentication status
    user_is_authenticated = auth_manager.is_authenticated()
    user = auth_manager.user
    user_spreadsheet_id = user.get_active_spreadsheet_id() if user else None

    logger.info(f"Authentication status: {user_is_authenticated}")
    logger.info(f"User spreadsheet ID: {user_spreadsheet_id}")

    # If not authenticated, show login screen
    if not user_is_authenticated:
        logger.info("User not authenticated, showing login screen")
        return render_template("login.html")

    # If no spreadsheet set, show setup screen
    if not user_spreadsheet_id:
        logger.info("No spreadsheet configured, showing setup screen")
        return render_template("setup.html", is_authenticated=user_is_authenticated)

    # Normal app flow with user's spreadsheet
    try:
        card_sets = read_all_card_sets(user_spreadsheet_id)
        logger.info(f"Found {len(card_sets)} card sets in spreadsheet {user_spreadsheet_id}")
        for card_set in card_sets:
            logger.info(f"  - {card_set.name}: {card_set.card_count} cards")
    except Exception as e:
        logger.error(f"Error reading card sets from spreadsheet {user_spreadsheet_id}: {e}")
        card_sets = []

    return render_template(
        "index.html",
        is_authenticated=user_is_authenticated,
        tabs=card_sets,
        user_spreadsheet_id=user_spreadsheet_id,
    )
