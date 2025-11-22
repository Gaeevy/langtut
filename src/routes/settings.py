"""
Settings routes for the Language Learning Flashcard App.

Handles user settings and spreadsheet configuration.
"""

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from src.gsheet import extract_spreadsheet_id, read_all_card_sets, validate_spreadsheet_access
from src.session_manager import SessionKeys as sk
from src.session_manager import SessionManager as sm
from src.user_manager import get_current_user, set_user_spreadsheet

# Create blueprint
settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/settings")
def settings():
    """Display user settings page."""
    # Check authentication
    if not sm.has(sk.AUTH_CREDENTIALS):
        return redirect(url_for("auth.auth"))

    # Get current user and their active spreadsheet
    user = get_current_user()
    current_spreadsheet_id = None

    if user:
        active_spreadsheet = user.get_active_spreadsheet()
        if active_spreadsheet:
            current_spreadsheet_id = active_spreadsheet.spreadsheet_id
            current_spreadsheet_name = active_spreadsheet.spreadsheet_name

    return render_template(
        "settings.html",
        user=user,
        current_spreadsheet_id=current_spreadsheet_id,
        current_spreadsheet_name=current_spreadsheet_name,
    )


@settings_bp.route("/validate-spreadsheet", methods=["POST"])
def validate_spreadsheet():
    """Validate access to a Google Spreadsheet."""
    # Check authentication
    if not sm.has(sk.AUTH_CREDENTIALS):
        return jsonify({"success": False, "error": "Not authenticated"})

    spreadsheet_url = request.json.get("spreadsheet_url", "").strip()

    if not spreadsheet_url:
        return jsonify({"success": False, "error": "Spreadsheet URL is required"})

    try:
        # Extract spreadsheet ID from URL
        spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)

        if not spreadsheet_id:
            return jsonify({"success": False, "error": "Invalid spreadsheet URL"})

        # Validate access to the spreadsheet
        spreadsheet_property = validate_spreadsheet_access(spreadsheet_id)
        spreadsheet_name = spreadsheet_property[3]
        set_user_spreadsheet(spreadsheet_id, spreadsheet_url, spreadsheet_name)

        if not spreadsheet_property:
            return jsonify(
                {
                    "success": False,
                    "error": "Cannot access spreadsheet. Make sure it is shared publicly or with your Google account.",
                }
            )

        # Try to read card sets to validate structure
        try:
            card_sets = read_all_card_sets(spreadsheet_id)
            if not card_sets:
                return jsonify(
                    {"success": False, "error": "No valid card sets found in the spreadsheet"}
                )

            return jsonify(
                {
                    "success": True,
                    "spreadsheet_id": spreadsheet_id,
                    "spreadsheet_name": spreadsheet_name,
                    "card_sets": [
                        {"name": cs.name, "card_count": len(cs.cards)} for cs in card_sets
                    ],
                }
            )

        except Exception as e:
            return jsonify({"success": False, "error": f"Spreadsheet structure is invalid: {e!s}"})

    except Exception as e:
        return jsonify({"success": False, "error": f"Error validating spreadsheet: {e!s}"})


@settings_bp.route("/set-spreadsheet", methods=["POST"])
def set_spreadsheet():
    """Set the user's active spreadsheet."""
    # Check authentication
    if not sm.has(sk.AUTH_CREDENTIALS):
        return jsonify({"success": False, "error": "Not authenticated"})

    spreadsheet_id = request.json.get("spreadsheet_id", "").strip()

    if not spreadsheet_id:
        return jsonify({"success": False, "error": "Spreadsheet ID is required"})

    try:
        # Set the user's spreadsheet
        success = set_user_spreadsheet(spreadsheet_id)

        if success:
            return jsonify({"success": True, "message": "Spreadsheet set successfully"})
        else:
            return jsonify({"success": False, "error": "Failed to set spreadsheet"})

    except Exception as e:
        return jsonify({"success": False, "error": f"Error setting spreadsheet: {e!s}"})


@settings_bp.route("/reset-spreadsheet", methods=["POST"])
def reset_spreadsheet():
    """Reset the user's spreadsheet to the default."""
    # Check authentication
    if not sm.has(sk.AUTH_CREDENTIALS):
        return jsonify({"success": False, "error": "Not authenticated"})

    try:
        # Reset to None (no spreadsheet)
        success = set_user_spreadsheet(None)

        if success:
            return jsonify({"success": True, "message": "Spreadsheet reset successfully"})
        else:
            return jsonify({"success": False, "error": "Failed to reset spreadsheet"})

    except Exception as e:
        return jsonify({"success": False, "error": f"Error resetting spreadsheet: {e!s}"})
