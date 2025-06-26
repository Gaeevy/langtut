"""
API routes for the Language Learning Flashcard App.

Handles API endpoints for text-to-speech and other services.
"""

import logging
from typing import Any

from flask import Blueprint, jsonify, request

from src.config import settings
from src.tts_service import TTSService

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
        logger.info(f'  Caching enabled: {bool(spreadsheet_id and sheet_gid is not None)}')

        result = {'success': True, 'audio': {}}

        # Generate speech for word if provided
        if word:
            logger.info(f'🎯 Generating TTS for word: "{word}"')
            if spreadsheet_id and sheet_gid is not None:
                # Use caching
                word_audio = tts_service.generate_speech_with_cache(
                    word, spreadsheet_id, sheet_gid, voice_name
                )
                logger.info(f'🎯 TTS word with cache: {word} -> {bool(word_audio)}')
            else:
                # No caching
                word_audio = tts_service.generate_speech_base64(word, voice_name)
                logger.info(f'🎯 TTS word without cache: {word} -> {bool(word_audio)}')

            if word_audio:
                result['audio']['word'] = {'text': word, 'audio_base64': word_audio}
                logger.info(
                    f'✅ Word audio generated successfully (length: {len(word_audio)} chars)'
                )
            else:
                logger.warning(f'❌ Failed to generate word audio for: "{word}"')

        # Generate speech for example if provided
        if example:
            logger.info(f'🎯 Generating TTS for example: "{example}"')
            if spreadsheet_id and sheet_gid is not None:
                # Use caching
                example_audio = tts_service.generate_speech_with_cache(
                    example, spreadsheet_id, sheet_gid, voice_name
                )
                logger.info(f'🎯 TTS example with cache: {example} -> {bool(example_audio)}')
            else:
                # No caching
                example_audio = tts_service.generate_speech_base64(example, voice_name)
                logger.info(f'🎯 TTS example without cache: {example} -> {bool(example_audio)}')

            if example_audio:
                result['audio']['example'] = {'text': example, 'audio_base64': example_audio}
                logger.info(
                    f'✅ Example audio generated successfully (length: {len(example_audio)} chars)'
                )
            else:
                logger.warning(f'❌ Failed to generate example audio for: "{example}"')

        if not result['audio']:
            logger.warning('No audio generated for any provided text')
            return jsonify(
                {'success': False, 'error': 'No valid text provided for speech generation'}
            ), 400

        logger.info(
            f'✅ TTS speak-card completed successfully. Generated audio for: {list(result["audio"].keys())}'
        )
        return jsonify(result)

    except Exception as e:
        logger.error(f'TTS card generation error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': f'Speech generation failed: {e!s}'}), 500
