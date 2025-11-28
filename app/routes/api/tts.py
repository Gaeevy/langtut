"""
TTS (Text-to-Speech) API routes.

Handles all text-to-speech related endpoints.
"""

import logging
from typing import Any

from flask import Blueprint, jsonify, request

from app.config import config
from app.services.tts import TTSService

logger = logging.getLogger(__name__)

# Create blueprint (will be nested under /api/)
tts_bp = Blueprint("tts", __name__, url_prefix="/tts")

# Initialize TTS service
tts_service = TTSService()


@tts_bp.route("/status")
def status() -> dict[str, Any]:
    """Get the status of the TTS service.

    Returns:
        JSON with availability status and configuration
    """
    try:
        # Check if TTS is enabled in configuration
        if not config.tts_enabled:
            return jsonify({"available": False, "reason": "TTS is disabled in configuration"})

        # Check if TTS service is properly configured
        is_available = tts_service.is_available()

        if not is_available:
            return jsonify({"available": False, "reason": "TTS service is not properly configured"})

        return jsonify(
            {
                "available": True,
                "language": config.tts_language_code,
                "voice": config.tts_voice_name,
            }
        )

    except Exception as e:
        logger.error(f"TTS status check failed: {e}", exc_info=True)
        return jsonify({"available": False, "reason": f"TTS service error: {e!s}"})


@tts_bp.route("/speak", methods=["POST"])
def speak() -> dict[str, Any]:
    """Generate speech for the provided text.

    Request body:
        text: Text to convert to speech
        voice_name: Optional voice name override

    Returns:
        JSON with base64 encoded audio
    """
    try:
        data = request.get_json()
        if not data or "text" not in data:
            return jsonify({"success": False, "error": "Text is required"}), 400

        text = data["text"].strip()
        if not text:
            return jsonify({"success": False, "error": "Text cannot be empty"}), 400

        # Generate speech as base64
        audio_base64 = tts_service.generate_speech_base64(text, data.get("voice_name"))

        if audio_base64 is None:
            return jsonify({"success": False, "error": "Failed to generate speech"}), 500

        return jsonify({"success": True, "audio_base64": audio_base64})

    except Exception as e:
        logger.error(f"TTS generation error: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"Speech generation failed: {e!s}"}), 500


@tts_bp.route("/speak-card", methods=["POST"])
def speak_card() -> dict[str, Any]:
    """Generate speech for card content (word and example).

    Request body:
        word: Word text to speak
        example: Example sentence to speak
        voice_name: Optional voice name override
        spreadsheet_id: Spreadsheet ID for caching
        sheet_gid: Sheet GID for caching

    Returns:
        JSON with base64 encoded audio for word and example
    """
    try:
        data = request.get_json()
        if not data:
            logger.warning("No JSON data provided in speak-card request")
            return jsonify({"success": False, "error": "Card data is required"}), 400

        word = data.get("word", "").strip()
        example = data.get("example", "").strip()
        voice_name = data.get("voice_name")
        spreadsheet_id = data.get("spreadsheet_id")
        sheet_gid = data.get("sheet_gid")

        logger.debug(
            f'TTS speak-card: word="{word}", example="{example[:30] if example else ""}..."'
        )

        result = {"success": True, "audio": {}}

        # Generate speech for word if provided
        if word:
            word_audio = tts_service.text_to_speech(word, spreadsheet_id, sheet_gid, voice_name)
            if word_audio:
                result["audio"]["word"] = {"text": word, "audio_base64": word_audio}
            else:
                logger.warning(f'❌ Failed to generate word audio for: "{word}"')

        # Generate speech for example if provided
        if example:
            example_audio = tts_service.text_to_speech(
                example, spreadsheet_id, sheet_gid, voice_name
            )
            if example_audio:
                result["audio"]["example"] = {"text": example, "audio_base64": example_audio}
            else:
                logger.warning(f'❌ Failed to generate example audio for: "{example}"')

        if not result["audio"]:
            logger.warning("No audio generated for any provided text")
            return jsonify(
                {"success": False, "error": "No valid text provided for speech generation"}
            ), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f"TTS card generation error: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"Speech generation failed: {e!s}"}), 500
