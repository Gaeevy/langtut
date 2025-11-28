"""
Cards API routes.

Handles card data endpoints for listening mode.
"""

import logging
import random
from typing import Any

from flask import Blueprint, jsonify

from src.gsheet import read_card_set
from src.services.auth_manager import auth_manager

logger = logging.getLogger(__name__)

# Create blueprint (will be nested under /api/)
cards_bp = Blueprint("cards", __name__, url_prefix="/cards")


@cards_bp.route("/<tab_name>")
@auth_manager.require_auth_api
def get_for_listening(tab_name: str) -> dict[str, Any]:
    """Get all cards from a card set for listening mode.

    Args:
        tab_name: Name of the worksheet/tab to fetch cards from

    Returns:
        JSON with shuffled cards containing word and example fields
    """
    logger.info(f"Loading cards for listening mode: {tab_name}")

    try:
        # Get user's spreadsheet ID
        user = auth_manager.user
        active_spreadsheet = user.get_active_spreadsheet()
        if not active_spreadsheet:
            logger.warning("No spreadsheet configured for user")
            return jsonify({"success": False, "error": "No spreadsheet configured"}), 400

        user_spreadsheet_id = active_spreadsheet.spreadsheet_id
        logger.info(f"Using spreadsheet: {user_spreadsheet_id}")

        # Read card set from Google Sheets
        card_set = read_card_set(worksheet_name=tab_name, spreadsheet_id=user_spreadsheet_id)

        if not card_set:
            logger.error(f'Card set "{tab_name}" not found in spreadsheet {user_spreadsheet_id}')
            return jsonify({"success": False, "error": f'Card set "{tab_name}" not found'}), 404

        if not card_set.cards:
            logger.warning(f'Card set "{tab_name}" is empty')
            return jsonify({"success": False, "error": f'Card set "{tab_name}" is empty'}), 400

        logger.info(f'Found {len(card_set.cards)} cards in "{tab_name}"')

        # Extract only fields needed for listening (word and example)
        cards_for_listening = []
        for card in card_set.cards:
            # Only include cards with both word and example text
            if card.word and card.word.strip() and card.example and card.example.strip():
                cards_for_listening.append(
                    {"id": card.id, "word": card.word.strip(), "example": card.example.strip()}
                )
            else:
                logger.debug(f"Skipping card {card.id}: missing word or example")

        if not cards_for_listening:
            logger.warning(f'No valid cards for listening in "{tab_name}"')
            return jsonify(
                {"success": False, "error": f'No cards with audio content found in "{tab_name}"'}
            ), 400

        # Always shuffle cards for listening mode
        random.shuffle(cards_for_listening)
        logger.info(f"Shuffled {len(cards_for_listening)} cards for listening mode")

        response = {
            "success": True,
            "tab_name": card_set.name,
            "sheet_gid": card_set.gid,
            "cards": cards_for_listening,
            "total_count": len(cards_for_listening),
            "original_count": len(card_set.cards),
        }

        logger.info(f"Returning {len(cards_for_listening)} shuffled cards for listening")
        return jsonify(response)

    except Exception as e:
        logger.error(f"Error fetching cards for listening: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"Failed to fetch cards: {e!s}"}), 500
