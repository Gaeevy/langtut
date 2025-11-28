"""
Language settings API routes.

Handles language configuration endpoints for spreadsheets.
"""

import logging
from typing import Any

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from app.database import db
from app.models import SpreadsheetLanguages
from app.services.auth_manager import auth_manager

logger = logging.getLogger(__name__)

# Create blueprint (will be nested under /api/)
language_bp = Blueprint("language", __name__, url_prefix="/language-settings")


@language_bp.route("", methods=["GET"])
@auth_manager.require_auth_api
def get_settings() -> dict[str, Any]:
    """Get current language settings for the user's active spreadsheet.

    Returns:
        JSON with language settings (original, target, hint languages)
    """
    try:
        user = auth_manager.user
        active_spreadsheet = user.get_active_spreadsheet()
        if not active_spreadsheet:
            logger.warning(f"No active spreadsheet found for user {user.email}")
            return jsonify({"success": False, "error": "No active spreadsheet found"}), 404

        # Get language settings using enhanced models
        properties = active_spreadsheet.get_properties()
        language_settings = properties.language

        logger.info(
            f"Retrieved language settings for user {user.email}: {language_settings.to_dict()}"
        )

        return jsonify(
            {
                "success": True,
                "language_settings": language_settings.to_dict(),
                "metadata": {
                    "spreadsheet_id": active_spreadsheet.spreadsheet_id,
                    "is_valid_configuration": language_settings.is_valid_configuration(),
                    "model_version": "enhanced",
                },
            }
        )

    except Exception as e:
        logger.error(f"Error getting language settings: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@language_bp.route("", methods=["POST"])
@auth_manager.require_auth_api
def save_settings() -> dict[str, Any]:
    """Save language settings for the user's active spreadsheet.

    Request body:
        language_settings: Object with original, target, hint language codes

    Returns:
        JSON with saved settings and metadata
    """
    try:
        user = auth_manager.user
        active_spreadsheet = user.get_active_spreadsheet()
        if not active_spreadsheet:
            logger.warning(f"No active spreadsheet found for user {user.email}")
            return jsonify({"success": False, "error": "No active spreadsheet found"}), 404

        # Get language settings from request
        data = request.get_json()
        if not data:
            logger.warning("No JSON data provided in request")
            return jsonify({"success": False, "error": "JSON data is required"}), 400

        logger.info(f"Received language settings data: {data}")

        # Extract language settings - support both formats
        language_data = data.get("language_settings") or data.get("language")
        if not language_data:
            return jsonify(
                {
                    "success": False,
                    "error": "Language settings are required",
                    "expected_format": {
                        "language_settings": {
                            "original": "language_code",
                            "target": "language_code",
                            "hint": "language_code",
                        }
                    },
                }
            ), 400

        # Validate using SpreadsheetLanguages model
        try:
            if isinstance(language_data, dict):
                new_language_settings = SpreadsheetLanguages.from_dict(language_data)
            else:
                new_language_settings = SpreadsheetLanguages(**language_data)

            logger.info(f"Validated language settings: {new_language_settings.to_dict()}")

        except ValidationError as e:
            logger.warning(f"Validation error for language settings: {e}")
            return jsonify(
                {
                    "success": False,
                    "error": "Invalid language settings",
                    "validation_errors": [
                        {
                            "field": error["loc"][0] if error["loc"] else "unknown",
                            "message": error["msg"],
                            "invalid_value": error.get("input"),
                        }
                        for error in e.errors()
                    ],
                    "expected_format": {
                        "original": 'Language code (2-5 chars, e.g., "ru", "en")',
                        "target": 'Language code (2-5 chars, e.g., "pt", "fr")',
                        "hint": 'Language code (2-5 chars, e.g., "en", "es")',
                    },
                }
            ), 400

        except (TypeError, ValueError) as e:
            logger.warning(f"Type/Value error for language settings: {e}")
            return jsonify(
                {
                    "success": False,
                    "error": f"Invalid language settings format: {e!s}",
                    "expected_format": {"original": "string", "target": "string", "hint": "string"},
                }
            ), 400

        # Business logic validation
        if not new_language_settings.is_valid_configuration():
            logger.warning("Language configuration has duplicate values")
            return jsonify(
                {
                    "success": False,
                    "error": "Language configuration cannot have duplicate values",
                    "current_settings": new_language_settings.to_dict(),
                    "suggestion": "Please ensure original, target, and hint languages are different",
                }
            ), 400

        # Get current settings for comparison
        current_properties = active_spreadsheet.get_properties()
        current_language_settings = current_properties.language

        # Update properties with new language settings
        updated_properties = active_spreadsheet.get_properties()
        updated_properties.language = new_language_settings
        active_spreadsheet.set_properties(updated_properties)

        # Commit changes
        db.session.commit()

        logger.info(f"Language settings saved for user {user.email}")
        logger.info(f"  Previous: {current_language_settings.to_dict()}")
        logger.info(f"  New: {new_language_settings.to_dict()}")

        return jsonify(
            {
                "success": True,
                "message": "Language settings saved successfully",
                "language_settings": new_language_settings.to_dict(),
                "metadata": {
                    "spreadsheet_id": active_spreadsheet.spreadsheet_id,
                    "previous_settings": current_language_settings.to_dict(),
                    "is_valid_configuration": new_language_settings.is_valid_configuration(),
                    "model_version": "enhanced",
                },
            }
        )

    except Exception as e:
        logger.error(f"Error saving language settings: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@language_bp.route("/validate", methods=["POST"])
def validate_settings() -> dict[str, Any]:
    """Validate language settings without saving them.

    Request body:
        language_settings: Object with original, target, hint language codes

    Returns:
        JSON with validation result and any errors
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "JSON data is required"}), 400

        # Extract language settings
        language_data = data.get("language_settings") or data.get("language")
        if not language_data:
            return jsonify({"success": False, "error": "Language settings are required"}), 400

        # Validate using SpreadsheetLanguages model
        try:
            if isinstance(language_data, dict):
                language_settings = SpreadsheetLanguages.from_dict(language_data)
            else:
                language_settings = SpreadsheetLanguages(**language_data)

            return jsonify(
                {
                    "success": True,
                    "valid": True,
                    "language_settings": language_settings.to_dict(),
                    "is_valid_configuration": language_settings.is_valid_configuration(),
                    "warnings": []
                    if language_settings.is_valid_configuration()
                    else ["Language configuration has duplicate values"],
                }
            )

        except ValidationError as e:
            return jsonify(
                {
                    "success": True,
                    "valid": False,
                    "validation_errors": [
                        {
                            "field": error["loc"][0] if error["loc"] else "unknown",
                            "message": error["msg"],
                            "invalid_value": error.get("input"),
                        }
                        for error in e.errors()
                    ],
                }
            )

    except Exception as e:
        logger.error(f"Error validating language settings: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
