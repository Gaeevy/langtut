"""
API routes for the Language Learning Flashcard App.

Handles API endpoints for text-to-speech and other services.
"""

import logging
import random
from typing import Any

from flask import Blueprint, jsonify, request, session

from src.config import settings
from src.gsheet import read_card_set
from src.tts_service import TTSService
from src.user_manager import get_user_spreadsheet_id, is_authenticated

# Create logger
logger = logging.getLogger(__name__)

# Create blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Initialize TTS service
tts_service = TTSService()


@api_bp.route('/tts/status')
def tts_status() -> dict[str, Any]:
    """Get the status of the TTS service."""
    logger.info('=== TTS STATUS API ===')
    logger.info(f'Request from: {request.remote_addr}')
    logger.info(f'User agent: {request.headers.get("User-Agent", "Unknown")}')

    try:
        # Check if TTS is enabled in configuration
        tts_enabled = settings.get('TTS_ENABLED', False)
        logger.info(f'TTS enabled in config: {tts_enabled}')

        if not tts_enabled:
            response = {'available': False, 'reason': 'TTS is disabled in configuration'}
            logger.info(f'TTS status response: {response}')
            return jsonify(response)

        # Check if TTS service is properly configured
        is_available = tts_service.is_available()
        logger.info(f'TTS service available: {is_available}')

        if not is_available:
            response = {'available': False, 'reason': 'TTS service is not properly configured'}
            logger.info(f'TTS status response: {response}')
            return jsonify(response)

        response = {
            'available': True,
            'language': settings.get('TTS_LANGUAGE_CODE', 'pt-PT'),
            'voice': settings.get('TTS_VOICE_NAME', 'pt-PT-Standard-A'),
        }
        logger.info(f'TTS status response: {response}')
        return jsonify(response)

    except Exception as e:
        logger.error(f'TTS status check failed: {e}', exc_info=True)
        response = {'available': False, 'reason': f'TTS service error: {e!s}'}
        return jsonify(response)


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
    logger.info('=== TTS SPEAK-CARD API ===')
    logger.info(f'Request from: {request.remote_addr}')
    logger.info(f'User agent: {request.headers.get("User-Agent", "Unknown")}')

    try:
        # Get card data from request
        data = request.get_json()
        if not data:
            logger.warning('No JSON data provided in request')
            return jsonify({'success': False, 'error': 'Card data is required'}), 400

        word = data.get('word', '').strip()
        example = data.get('example', '').strip()
        voice_name = data.get('voice_name')
        spreadsheet_id = data.get('spreadsheet_id')
        sheet_gid = data.get('sheet_gid')

        logger.info('TTS request parameters:')
        logger.info(f'  Word: "{word}"')
        logger.info(f'  Example: "{example}"')
        logger.info(f'  Voice: {voice_name}')
        logger.info(f'  Spreadsheet ID: {spreadsheet_id}')
        logger.info(f'  Sheet GID: {sheet_gid}')

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
    logger.info('=== CARDS API FOR LISTENING ===')
    logger.info(f'Request from: {request.remote_addr}')
    logger.info(f'Tab name: {tab_name}')
    logger.info(f'User agent: {request.headers.get("User-Agent", "Unknown")}')

    try:
        # Check authentication
        if not is_authenticated():
            logger.warning('User not authenticated')
            return jsonify({'success': False, 'error': 'Authentication required'}), 401

        # Get user's spreadsheet ID
        user_spreadsheet_id = get_user_spreadsheet_id(session)
        if not user_spreadsheet_id:
            logger.warning('No spreadsheet configured for user')
            return jsonify({'success': False, 'error': 'No spreadsheet configured'}), 400

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
