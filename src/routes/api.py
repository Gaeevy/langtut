"""
API routes for the Language Learning Flashcard App.

Handles API endpoints for text-to-speech and other services.
"""

import logging
import random
from typing import Any

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from src.config import config
from src.database import db
from src.gsheet import read_card_set
from src.models import SpreadsheetLanguages
from src.tts_service import TTSService
from src.user_manager import get_current_user, is_authenticated

# Create logger
logger = logging.getLogger(__name__)

# Create blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Initialize TTS service
tts_service = TTSService()


@api_bp.route('/tts/status')
def tts_status() -> dict[str, Any]:
    """Get the status of the TTS service."""
    try:
        # Check if TTS is enabled in configuration
        if not config.tts_enabled:
            return jsonify({'available': False, 'reason': 'TTS is disabled in configuration'})

        # Check if TTS service is properly configured
        is_available = tts_service.is_available()

        if not is_available:
            return jsonify({'available': False, 'reason': 'TTS service is not properly configured'})

        return jsonify(
            {
                'available': True,
                'language': config.tts_language_code,
                'voice': config.tts_voice_name,
            }
        )

    except Exception as e:
        logger.error(f'TTS status check failed: {e}', exc_info=True)
        return jsonify({'available': False, 'reason': f'TTS service error: {e!s}'})


@api_bp.route('/tts/speak', methods=['POST'])
def generate_speech() -> dict[str, Any]:
    """Generate speech for the provided text."""
    try:
        # Get text from request
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'success': False, 'error': 'Text is required'}), 400

        text = data['text'].strip()
        if not text:
            return jsonify({'success': False, 'error': 'Text cannot be empty'}), 400

        # Generate speech as base64
        audio_base64 = tts_service.generate_speech_base64(text, data.get('voice_name'))

        if audio_base64 is None:
            return jsonify({'success': False, 'error': 'Failed to generate speech'}), 500

        # Return base64 encoded audio
        return jsonify({'success': True, 'audio_base64': audio_base64})

    except Exception as e:
        print(f'TTS generation error: {e}')
        return jsonify({'success': False, 'error': f'Speech generation failed: {e!s}'}), 500


@api_bp.route('/tts/speak-card', methods=['POST'])
def speak_card_content() -> dict[str, Any]:
    """Generate speech for card content (word and example)."""
    try:
        # Get card data from request
        data = request.get_json()
        if not data:
            logger.warning('No JSON data provided in speak-card request')
            return jsonify({'success': False, 'error': 'Card data is required'}), 400

        word = data.get('word', '').strip()
        example = data.get('example', '').strip()
        voice_name = data.get('voice_name')
        spreadsheet_id = data.get('spreadsheet_id')
        sheet_gid = data.get('sheet_gid')

        logger.debug(f'TTS speak-card: word="{word}", example="{example[:30]}..."')

        result = {'success': True, 'audio': {}}

        # Generate speech for word if provided
        if word:
            word_audio = tts_service.text_to_speech(word, spreadsheet_id, sheet_gid, voice_name)

            if word_audio:
                result['audio']['word'] = {'text': word, 'audio_base64': word_audio}
            else:
                logger.warning(f'❌ Failed to generate word audio for: "{word}"')

        # Generate speech for example if provided
        if example:
            example_audio = tts_service.text_to_speech(
                example, spreadsheet_id, sheet_gid, voice_name
            )

            if example_audio:
                result['audio']['example'] = {'text': example, 'audio_base64': example_audio}
            else:
                logger.warning(f'❌ Failed to generate example audio for: "{example}"')

        if not result['audio']:
            logger.warning('No audio generated for any provided text')
            return jsonify(
                {'success': False, 'error': 'No valid text provided for speech generation'}
            ), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f'TTS card generation error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': f'Speech generation failed: {e!s}'}), 500


@api_bp.route('/cards/<tab_name>')
def get_card_set_for_listening(tab_name: str) -> dict[str, Any]:
    """Get all cards from a card set for listening mode."""
    logger.info(f'Loading cards for listening mode: {tab_name}')

    try:
        # Check authentication
        if not is_authenticated():
            logger.warning('User not authenticated')
            return jsonify({'success': False, 'error': 'Authentication required'}), 401

        # Get user's spreadsheet ID using enhanced model approach
        user = get_current_user()
        if not user:
            logger.warning('No user found')
            return jsonify({'success': False, 'error': 'User not found'}), 401

        active_spreadsheet = user.get_active_spreadsheet()
        if not active_spreadsheet:
            logger.warning('No spreadsheet configured for user')
            return jsonify({'success': False, 'error': 'No spreadsheet configured'}), 400

        user_spreadsheet_id = active_spreadsheet.spreadsheet_id

        logger.info(f'Using spreadsheet: {user_spreadsheet_id}')

        # Read card set from Google Sheets
        card_set = read_card_set(worksheet_name=tab_name, spreadsheet_id=user_spreadsheet_id)

        if not card_set:
            logger.error(f'Card set "{tab_name}" not found in spreadsheet {user_spreadsheet_id}')
            return jsonify({'success': False, 'error': f'Card set "{tab_name}" not found'}), 404

        if not card_set.cards:
            logger.warning(f'Card set "{tab_name}" is empty')
            return jsonify({'success': False, 'error': f'Card set "{tab_name}" is empty'}), 400

        logger.info(f'Found {len(card_set.cards)} cards in "{tab_name}"')

        # Extract only the fields needed for listening (word and example)
        cards_for_listening = []
        for card in card_set.cards:
            # Only include cards that have both word and example text
            if card.word and card.word.strip() and card.example and card.example.strip():
                cards_for_listening.append(
                    {'id': card.id, 'word': card.word.strip(), 'example': card.example.strip()}
                )
            else:
                logger.debug(f'Skipping card {card.id}: missing word or example')

        if not cards_for_listening:
            logger.warning(f'No valid cards for listening in "{tab_name}"')
            return jsonify(
                {'success': False, 'error': f'No cards with audio content found in "{tab_name}"'}
            ), 400

        # Always shuffle cards for listening mode
        random.shuffle(cards_for_listening)
        logger.info(f'Shuffled {len(cards_for_listening)} cards for listening mode')

        # Prepare response
        response = {
            'success': True,
            'tab_name': card_set.name,
            'sheet_gid': card_set.gid,
            'cards': cards_for_listening,
            'total_count': len(cards_for_listening),
            'original_count': len(card_set.cards),  # Total cards before filtering
        }

        logger.info(f'Returning {len(cards_for_listening)} shuffled cards for listening')
        return jsonify(response)

    except Exception as e:
        logger.error(f'Error fetching cards for listening: {e}', exc_info=True)
        return jsonify({'success': False, 'error': f'Failed to fetch cards: {e!s}'}), 500


@api_bp.route('/language-settings', methods=['GET'])
def get_language_settings() -> dict[str, Any]:
    """Get current language settings for the user's active spreadsheet."""

    try:
        # Check authentication
        user = get_current_user()
        if not user:
            logger.warning('User not authenticated')
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        # Get user's active spreadsheet
        active_spreadsheet = user.get_active_spreadsheet()
        if not active_spreadsheet:
            logger.warning(f'No active spreadsheet found for user {user.email}')
            return jsonify({'success': False, 'error': 'No active spreadsheet found'}), 404

        # Get language settings using the enhanced models
        properties = active_spreadsheet.get_properties()
        language_settings = properties.language

        logger.info(
            f'Retrieved language settings for user {user.email}: {language_settings.to_dict()}'
        )

        return jsonify(
            {
                'success': True,
                'language_settings': language_settings.to_dict(),
                'metadata': {
                    'spreadsheet_id': active_spreadsheet.spreadsheet_id,
                    'is_valid_configuration': language_settings.is_valid_configuration(),
                    'model_version': 'enhanced',
                },
            }
        )

    except Exception as e:
        logger.error(f'Error getting language settings: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/language-settings', methods=['POST'])
def save_language_settings() -> dict[str, Any]:
    """Save language settings for the user's active spreadsheet with Pydantic validation."""

    try:
        # Check authentication
        user = get_current_user()
        if not user:
            logger.warning('User not authenticated')
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        # Get user's active spreadsheet
        active_spreadsheet = user.get_active_spreadsheet()
        if not active_spreadsheet:
            logger.warning(f'No active spreadsheet found for user {user.email}')
            return jsonify({'success': False, 'error': 'No active spreadsheet found'}), 404

        # Get language settings from request
        data = request.get_json()
        if not data:
            logger.warning('No JSON data provided in request')
            return jsonify({'success': False, 'error': 'JSON data is required'}), 400

        logger.info(f'Received language settings data: {data}')

        # Extract language settings - support both formats
        language_data = data.get('language_settings') or data.get('language')
        if not language_data:
            return jsonify(
                {
                    'success': False,
                    'error': 'Language settings are required',
                    'expected_format': {
                        'language_settings': {
                            'original': 'language_code',
                            'target': 'language_code',
                            'hint': 'language_code',
                        }
                    },
                }
            ), 400

        # Validate using SpreadsheetLanguages model
        try:
            if isinstance(language_data, dict):
                # Create SpreadsheetLanguages from dict with validation
                new_language_settings = SpreadsheetLanguages.from_dict(language_data)
            else:
                # Try to create directly (if it's already structured correctly)
                new_language_settings = SpreadsheetLanguages(**language_data)

            logger.info(f'Validated language settings: {new_language_settings.to_dict()}')

        except ValidationError as e:
            logger.warning(f'Validation error for language settings: {e}')
            return jsonify(
                {
                    'success': False,
                    'error': 'Invalid language settings',
                    'validation_errors': [
                        {
                            'field': error['loc'][0] if error['loc'] else 'unknown',
                            'message': error['msg'],
                            'invalid_value': error.get('input'),
                        }
                        for error in e.errors()
                    ],
                    'expected_format': {
                        'original': 'Language code (2-5 chars, e.g., "ru", "en")',
                        'target': 'Language code (2-5 chars, e.g., "pt", "fr")',
                        'hint': 'Language code (2-5 chars, e.g., "en", "es")',
                    },
                }
            ), 400

        except (TypeError, ValueError) as e:
            logger.warning(f'Type/Value error for language settings: {e}')
            return jsonify(
                {
                    'success': False,
                    'error': f'Invalid language settings format: {e!s}',
                    'expected_format': {'original': 'string', 'target': 'string', 'hint': 'string'},
                }
            ), 400

        # Additional business logic validation
        if not new_language_settings.is_valid_configuration():
            logger.warning('Language configuration has duplicate values')
            return jsonify(
                {
                    'success': False,
                    'error': 'Language configuration cannot have duplicate values',
                    'current_settings': new_language_settings.to_dict(),
                    'suggestion': 'Please ensure original, target, and hint languages are different',
                }
            ), 400

        # Get current settings for comparison
        current_properties = active_spreadsheet.get_properties()
        current_language_settings = current_properties.language

        # Update the properties with new language settings
        updated_properties = active_spreadsheet.get_properties()
        updated_properties.language = new_language_settings
        active_spreadsheet.set_properties(updated_properties)

        # Commit changes
        db.session.commit()

        logger.info(f'Language settings saved for user {user.email}')
        logger.info(f'  Previous: {current_language_settings.to_dict()}')
        logger.info(f'  New: {new_language_settings.to_dict()}')

        return jsonify(
            {
                'success': True,
                'message': 'Language settings saved successfully',
                'language_settings': new_language_settings.to_dict(),
                'metadata': {
                    'spreadsheet_id': active_spreadsheet.spreadsheet_id,
                    'previous_settings': current_language_settings.to_dict(),
                    'is_valid_configuration': new_language_settings.is_valid_configuration(),
                    'model_version': 'enhanced',
                },
            }
        )

    except Exception as e:
        logger.error(f'Error saving language settings: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/language-settings/validate', methods=['POST'])
def validate_language_settings() -> dict[str, Any]:
    """Validate language settings without saving them."""

    try:
        # Get language settings from request
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'JSON data is required'}), 400

        # Extract language settings
        language_data = data.get('language_settings') or data.get('language')
        if not language_data:
            return jsonify({'success': False, 'error': 'Language settings are required'}), 400

        # Validate using SpreadsheetLanguages model
        try:
            if isinstance(language_data, dict):
                language_settings = SpreadsheetLanguages.from_dict(language_data)
            else:
                language_settings = SpreadsheetLanguages(**language_data)

            return jsonify(
                {
                    'success': True,
                    'valid': True,
                    'language_settings': language_settings.to_dict(),
                    'is_valid_configuration': language_settings.is_valid_configuration(),
                    'warnings': []
                    if language_settings.is_valid_configuration()
                    else ['Language configuration has duplicate values'],
                }
            )

        except ValidationError as e:
            return jsonify(
                {
                    'success': True,
                    'valid': False,
                    'validation_errors': [
                        {
                            'field': error['loc'][0] if error['loc'] else 'unknown',
                            'message': error['msg'],
                            'invalid_value': error.get('input'),
                        }
                        for error in e.errors()
                    ],
                }
            )

    except Exception as e:
        logger.error(f'Error validating language settings: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500
