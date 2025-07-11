"""
Test routes for the Language Learning Flashcard App.

Handles testing and debugging functionality.
"""

from datetime import datetime
from typing import Any

from flask import Blueprint, jsonify, render_template

from src.config import SPREADSHEET_ID
from src.database import UserSpreadsheet, db
from src.gsheet import read_all_card_sets
from src.tts_service import TTSService
from src.user_manager import get_current_user

# Create blueprint
test_bp = Blueprint('test', __name__)

# Initialize TTS service for testing
tts_service = TTSService()


@test_bp.route('/test')
def test() -> dict[str, Any]:
    """Test basic functionality and return system status."""
    try:
        # Test Google Sheets access
        try:
            card_sets = read_all_card_sets(SPREADSHEET_ID)
            sheets_status = {
                'working': True,
                'card_sets_count': len(card_sets),
                'card_sets': [cs.name for cs in card_sets[:3]],  # First 3 for brevity
            }
        except Exception as e:
            sheets_status = {'working': False, 'error': str(e)}

        # Test TTS service
        try:
            tts_configured = tts_service.is_configured()
            if tts_configured:
                # Try a simple synthesis test
                test_audio = tts_service.generate_speech('teste')
                tts_status = {'configured': True, 'synthesis_test': test_audio is not None}
            else:
                tts_status = {'configured': False, 'synthesis_test': False}
        except Exception as e:
            tts_status = {'configured': False, 'synthesis_test': False, 'error': str(e)}

        return jsonify(
            {
                'success': True,
                'timestamp': str(datetime.now()),
                'services': {'google_sheets': sheets_status, 'text_to_speech': tts_status},
            }
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@test_bp.route('/test-tts')
def test_tts():
    """Render TTS testing page."""
    return render_template('test_tts.html')


@test_bp.route('/test-properties')
def test_properties() -> dict[str, Any]:
    """Test the new properties column (Phase 1: simple text field)."""
    try:
        # Get current user (if logged in)
        user = get_current_user()
        if not user:
            return jsonify(
                {
                    'success': False,
                    'error': 'User not logged in. Please authenticate first.',
                    'note': 'This test requires an authenticated user with spreadsheets.',
                }
            )

        # Get user's first spreadsheet for testing
        spreadsheet = UserSpreadsheet.query.filter_by(user_id=user.id).first()
        if not spreadsheet:
            return jsonify(
                {
                    'success': False,
                    'error': 'No spreadsheets found for user.',
                    'note': 'Add a spreadsheet first, then test properties.',
                }
            )

        # Phase 1: Simple test - just show the current value and set a test value
        current_value = spreadsheet.properties

        # Test setting a simple JSON string
        test_json = '{"language":{"original":"ru","target":"pt","hint":"en"}}'
        spreadsheet.properties = test_json
        db.session.commit()

        # Read it back
        updated_value = spreadsheet.properties

        return jsonify(
            {
                'success': True,
                'phase': 'Phase 1 - Basic Column Test',
                'user_id': user.id,
                'spreadsheet_id': spreadsheet.spreadsheet_id,
                'test_results': {
                    'original_value': current_value,
                    'test_value_set': test_json,
                    'updated_value': updated_value,
                    'column_works': updated_value == test_json,
                },
                'note': 'Phase 1: Simple text column working correctly',
            }
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
