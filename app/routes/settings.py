"""
Settings routes for the Language Learning Flashcard App.

Handles user settings and spreadsheet configuration.
"""

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from app.language_config import get_ui_language_codes, label_for_code
from app.services.auth_manager import auth_manager
from app.services.settings_service import SettingsService

service = SettingsService()


# Create blueprint
settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/settings")
@auth_manager.require_auth
def settings():
    """Display user settings page."""
    # Get current user and their active spreadsheet
    user = auth_manager.user

    active_spreadsheet = user.get_active_spreadsheet()
    if not active_spreadsheet:
        return redirect(url_for("index.home"))

    language_codes = get_ui_language_codes()
    language_labels = {code: label_for_code(code) for code in language_codes}

    return render_template(
        "settings.html",
        user=user,
        active_spreadsheet=active_spreadsheet,
        language_codes=language_codes,
        language_labels=language_labels,
    )


@settings_bp.route("/validate-spreadsheet", methods=["POST"])
@auth_manager.require_auth
def validate_spreadsheet():
    """Validate access to a Google Spreadsheet."""
    spreadsheet_url = request.json.get("spreadsheet_url", "").strip()
    result = service.validate_spreadsheet(auth_manager.user, spreadsheet_url)
    return jsonify(result.payload), result.status_code


@settings_bp.route("/set-spreadsheet", methods=["POST"])
@auth_manager.require_auth
def set_spreadsheet():
    """Set the user's active spreadsheet."""
    spreadsheet_id = request.json.get("spreadsheet_id", "").strip()
    result = service.set_spreadsheet(auth_manager.user, spreadsheet_id)
    return jsonify(result.payload), result.status_code


@settings_bp.route("/settings/activate-spreadsheet", methods=["POST"])
@auth_manager.require_auth
def activate_spreadsheet():
    """Activate a specific spreadsheet for the user."""
    spreadsheet_id = request.json.get("spreadsheet_id", "").strip()
    result = service.activate_spreadsheet(auth_manager.user, spreadsheet_id)
    return jsonify(result.payload), result.status_code


@settings_bp.route("/settings/rename-spreadsheet", methods=["POST"])
@auth_manager.require_auth
def rename_spreadsheet():
    """Rename a spreadsheet in user's list."""
    spreadsheet_id = request.json.get("spreadsheet_id", "").strip()
    new_name_raw = request.json.get("new_name", "")
    new_name_stripped = new_name_raw.strip()
    new_name = new_name_stripped if new_name_stripped else None

    result = service.rename_spreadsheet(auth_manager.user, spreadsheet_id, new_name)
    return jsonify(result.payload), result.status_code


@settings_bp.route("/settings/remove-spreadsheet", methods=["POST"])
@auth_manager.require_auth
def remove_spreadsheet():
    """Remove a spreadsheet from user's list."""
    spreadsheet_id = request.json.get("spreadsheet_id", "").strip()

    result = service.remove_spreadsheet(auth_manager.user, spreadsheet_id)
    return jsonify(result.payload), result.status_code
