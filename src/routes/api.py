"""
API routes for the Language Learning Flashcard App.

Handles API endpoints for text-to-speech and other services.
"""

import io
from typing import Any

from flask import Blueprint, Response, jsonify, request

from src.config import settings
from src.tts_service import TTSService

# Create blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Initialize TTS service
tts_service = TTSService()


@api_bp.route('/tts/status')
def tts_status() -> dict[str, Any]:
    """Get the status of the TTS service."""
    try:
        # Check if TTS is enabled in configuration
        tts_enabled = settings.get('TTS_ENABLED', False)

        if not tts_enabled:
            return jsonify({'available': False, 'reason': 'TTS is disabled in configuration'})

        # Check if TTS service is properly configured
        if not tts_service.is_configured():
            return jsonify({'available': False, 'reason': 'TTS service is not properly configured'})

        return jsonify(
            {
                'available': True,
                'language': settings.get('TTS_LANGUAGE_CODE', 'pt-PT'),
                'voice': settings.get('TTS_VOICE_NAME', 'pt-PT-Standard-A'),
            }
        )

    except Exception as e:
        return jsonify({'available': False, 'reason': f'TTS service error: {e!s}'})


@api_bp.route('/tts/speak', methods=['POST'])
def generate_speech() -> Response:
    """Generate speech for the provided text."""
    try:
        # Get text from request
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'error': 'Text is required'}), 400

        text = data['text'].strip()
        if not text:
            return jsonify({'error': 'Text cannot be empty'}), 400

        # Generate speech
        audio_content = tts_service.generate_speech(text)

        if audio_content is None:
            return jsonify({'error': 'Failed to generate speech'}), 500

        # Return audio as response
        return Response(
            io.BytesIO(audio_content),
            mimetype='audio/mpeg',
            headers={'Content-Disposition': 'attachment; filename=speech.mp3'},
        )

    except Exception as e:
        print(f'TTS generation error: {e}')
        return jsonify({'error': f'Speech generation failed: {e!s}'}), 500


@api_bp.route('/tts/speak-card', methods=['POST'])
def speak_card_content() -> Response:
    """Generate speech for card content (word and example)."""
    try:
        # Get card data from request
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Card data is required'}), 400

        content_type = data.get('type', 'word')  # 'word' or 'example'

        if content_type == 'word':
            text = data.get('word', '').strip()
        elif content_type == 'example':
            text = data.get('example', '').strip()
        else:
            return jsonify({'error': 'Invalid content type'}), 400

        if not text:
            return jsonify({'error': f'{content_type.capitalize()} text is required'}), 400

        # Generate speech
        audio_content = tts_service.generate_speech(text)

        if audio_content is None:
            return jsonify({'error': 'Failed to generate speech'}), 500

        # Return audio as response
        return Response(
            io.BytesIO(audio_content),
            mimetype='audio/mpeg',
            headers={'Content-Disposition': f'attachment; filename={content_type}.mp3'},
        )

    except Exception as e:
        print(f'TTS card generation error: {e}')
        return jsonify({'error': f'Speech generation failed: {e!s}'}), 500
