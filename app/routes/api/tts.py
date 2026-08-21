"""
TTS (Text-to-Speech) API routes.

Handles all text-to-speech related endpoints.
"""

from flask import Blueprint, jsonify, request

from app.services.auth_manager import auth_manager
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

    spreadsheet_value = data.get("spreadsheet_id")
    sheet_value = data.get("sheet_gid")
    spreadsheet_id = str(spreadsheet_value).strip() if spreadsheet_value is not None else None
    sheet_gid = str(sheet_value).strip() if sheet_value is not None else None

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


@tts_bp.route("/invalidate", methods=["POST"])
@auth_manager.require_auth_api
def invalidate():
    """Delete one clip from the current user's browser/GCS cache namespace."""
    data = request.get_json(silent=True) or {}
    text_value = data.get("text")
    spreadsheet_value = data.get("spreadsheet_id")
    sheet_value = data.get("sheet_gid")
    text = str(text_value).strip() if text_value is not None else ""
    spreadsheet_id = str(spreadsheet_value).strip() if spreadsheet_value is not None else ""
    sheet_gid = str(sheet_value).strip() if sheet_value is not None else ""

    if not text:
        return jsonify({"success": False, "error": "No text provided"}), 400
    if not spreadsheet_id or not sheet_gid:
        return jsonify({"success": False, "error": "Spreadsheet and sheet are required"}), 400

    user = auth_manager.user
    if not user or user.get_active_spreadsheet_id() != spreadsheet_id:
        return jsonify({"success": False, "error": "Spreadsheet is not active"}), 403

    try:
        invalidated = tts_service.invalidate_cache(text, spreadsheet_id, sheet_gid)
        return jsonify({"success": True, "invalidated": invalidated})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception:
        return jsonify({"success": False, "error": "Cache invalidation failed"}), 500
