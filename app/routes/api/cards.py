"""Cards API routes."""

from flask import Blueprint, jsonify

from app.services.auth_manager import auth_manager
from app.services.listening_cards_service import ListeningCardsService

# Create blueprint (will be nested under /api/)
cards_bp = Blueprint("cards", __name__, url_prefix="/cards")
service = ListeningCardsService()


@cards_bp.route("/<tab_name>")
@auth_manager.require_auth_api
def get_for_listening(tab_name: str):
    """Get all cards from a card set for listening mode.

    Args:
        tab_name: Name of the worksheet/tab to fetch cards from

    Returns:
        JSON with shuffled cards containing word and example fields
    """
    result = service.get_for_listening(auth_manager.user, tab_name)
    return jsonify(result.payload), result.status_code
