"""
Test routes for the Language Learning Flashcard App.

Handles testing and debugging functionality.
"""

from datetime import datetime
from typing import Any

from flask import Blueprint, jsonify, render_template

from app.config import config
from app.gsheet import read_all_card_sets
from app.services.tts import TTSService

# Create blueprint
test_bp = Blueprint("test", __name__)

# Initialize TTS service for testing
tts_service = TTSService()


@test_bp.route("/test")
def test() -> dict[str, Any]:
    """Test endpoint for checking application functionality."""
    try:
        # Test reading card sets
        card_sets = read_all_card_sets(config.spreadsheet_id)

        # Test Google Sheets access
        try:
            card_sets = read_all_card_sets(config.spreadsheet_id)
            sheets_status = {
                "working": True,
                "card_sets_count": len(card_sets),
                "card_sets": [cs.name for cs in card_sets[:3]],  # First 3 for brevity
            }
        except Exception as e:
            sheets_status = {"working": False, "error": str(e)}

        # Test TTS service
        try:
            tts_configured = tts_service.is_configured()
            if tts_configured:
                # Try a simple synthesis test
                test_audio = tts_service.generate_speech("teste")
                tts_status = {"configured": True, "synthesis_test": test_audio is not None}
            else:
                tts_status = {"configured": False, "synthesis_test": False}
        except Exception as e:
            tts_status = {"configured": False, "synthesis_test": False, "error": str(e)}

        # Count total cards
        total_cards = sum(len(cs.cards) for cs in card_sets)

        # Create test data
        test_data = {
            "status": "success",
            "sheets_status": sheets_status,
            "tts_status": tts_status,
            "timestamp": datetime.now().isoformat(),
            "card_sets": len(card_sets),
            "total_cards": total_cards,
            "spreadsheet_id": config.spreadsheet_id,
            "environment": "test",
            "health_check": True,
        }

        # Return test data
        return jsonify(test_data)

    except Exception as e:
        # Error handling
        return jsonify(
            {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "environment": "test",
                "health_check": False,
            }
        )


@test_bp.route("/test-tts")
def test_tts():
    """Test TTS functionality"""
    return render_template("test_tts.html")
