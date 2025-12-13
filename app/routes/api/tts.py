"""
TTS (Text-to-Speech) API routes.

Handles all text-to-speech related endpoints.
"""

from flask import Blueprint, jsonify, request

from app.services.tts import tts_service
from app.session_manager import SessionKeys, SessionManager

# Create blueprint (will be nested under /api/)
tts_bp = Blueprint("tts", __name__, url_prefix="/tts")


@tts_bp.route("/status", methods=["GET"])
def status():
    """Get TTS availability status."""
    sm = SessionManager()
    target_lang = sm.get(SessionKeys.TARGET_LANGUAGE)

    if not target_lang:
        return jsonify({"available": False, "error": "No target language in session"})

    try:
        return jsonify(
            {
                "available": tts_service.enabled,
                "language": tts_service.language_code,
                "voice": tts_service.voice_name,
            }
        )
    except ValueError as e:
        return jsonify({"available": False, "error": str(e)})


@tts_bp.route("/speak", methods=["POST"])
def speak():
    """
    Generate speech for single text.

    Voice is automatically resolved from session target language.

    Request:
        {
            "text": "olá",
            "spreadsheet_id": "optional",
            "sheet_gid": "optional"
        }

    Response:
        {
            "success": true,
            "audio_base64": "UklGRiQAAABXQVZF..."
        }
    """
    data = request.get_json()
    text = data.get("text", "").strip()

    if not text:
        return jsonify({"success": False, "error": "No text provided"}), 400

    spreadsheet_id = data.get("spreadsheet_id")
    sheet_gid = data.get("sheet_gid")

    try:
        audio_base64 = tts_service.text_to_speech(
            text=text, spreadsheet_id=spreadsheet_id, sheet_gid=sheet_gid
        )

        if audio_base64:
            return jsonify({"success": True, "audio_base64": audio_base64})
        else:
            return jsonify({"success": False, "error": "TTS generation failed"}), 500

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception:
        return jsonify({"success": False, "error": "Internal server error"}), 500
