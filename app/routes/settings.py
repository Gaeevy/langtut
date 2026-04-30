"""
Settings routes for the Language Learning Flashcard App.

Handles user settings and spreadsheet configuration.
"""

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from app.database import UserSpreadsheet
from app.gsheet import (
    extract_spreadsheet_id,
    read_all_card_sets,
    spreadsheet_editor_url,
    validate_spreadsheet_access,
)
from app.language_config import get_ui_language_codes, label_for_code
from app.services.auth_manager import auth_manager


def _spreadsheet_summary(user_spreadsheet: UserSpreadsheet) -> dict:
    """Build a JSON-serializable summary for the client's spreadsheet picker."""
    sid = user_spreadsheet.spreadsheet_id
    return {
        "spreadsheet_id": sid,
        "spreadsheet_name": user_spreadsheet.spreadsheet_name,
        "spreadsheet_url": user_spreadsheet.spreadsheet_url or spreadsheet_editor_url(sid),
        "is_active": user_spreadsheet.is_active,
    }


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

    if not spreadsheet_url:
        return jsonify({"success": False, "error": "Spreadsheet URL is required"})

    try:
        # Extract spreadsheet ID from URL
        spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)

        if not spreadsheet_id:
            return jsonify({"success": False, "error": "Invalid spreadsheet URL"})

        # Validate access and get spreadsheet name
        spreadsheet_name = validate_spreadsheet_access(spreadsheet_id)

        # Try to read card sets to validate structure
        card_sets = read_all_card_sets(spreadsheet_id)
        if not card_sets:
            return jsonify(
                {"success": False, "error": "No valid card sets found in the spreadsheet"}
            )

        # Save to user's account
        user = auth_manager.user
        user_spreadsheet = user.add_spreadsheet(spreadsheet_id, spreadsheet_url, spreadsheet_name)

        return jsonify(
            {
                "success": True,
                "spreadsheet": _spreadsheet_summary(user_spreadsheet),
                "id": user_spreadsheet.id,
                "spreadsheet_id": spreadsheet_id,
                "spreadsheet_name": spreadsheet_name,
                "card_sets": [{"name": cs.name, "card_count": len(cs.cards)} for cs in card_sets],
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": f"Error validating spreadsheet: {e!s}"})


@settings_bp.route("/set-spreadsheet", methods=["POST"])
@auth_manager.require_auth
def set_spreadsheet():
    """Set the user's active spreadsheet."""
    spreadsheet_id = request.json.get("spreadsheet_id", "").strip()

    if not spreadsheet_id:
        return jsonify({"success": False, "error": "Spreadsheet ID is required"})

    try:
        user = auth_manager.user

        # Add/update the user's spreadsheet
        user_spreadsheet = user.add_spreadsheet(spreadsheet_id)

        if user_spreadsheet:
            return jsonify({"success": True, "message": "Spreadsheet set successfully"})
        else:
            return jsonify({"success": False, "error": "Failed to set spreadsheet"})

    except Exception as e:
        return jsonify({"success": False, "error": f"Error setting spreadsheet: {e!s}"})


@settings_bp.route("/settings/activate-spreadsheet", methods=["POST"])
@auth_manager.require_auth
def activate_spreadsheet():
    """Activate a specific spreadsheet for the user."""
    spreadsheet_id = request.json.get("spreadsheet_id", "").strip()

    if not spreadsheet_id:
        return jsonify({"success": False, "error": "Spreadsheet ID is required"})

    try:
        user = auth_manager.user

        # Set the spreadsheet as active
        spreadsheet = user.activate_spreadsheet(spreadsheet_id)

        if spreadsheet:
            return jsonify(
                {
                    "success": True,
                    "message": "Spreadsheet activated successfully",
                    "spreadsheet": _spreadsheet_summary(spreadsheet),
                }
            )
        else:
            return jsonify({"success": False, "error": "Spreadsheet not found in user's list"})

    except Exception as e:
        return jsonify({"success": False, "error": f"Error activating spreadsheet: {e!s}"})


@settings_bp.route("/settings/rename-spreadsheet", methods=["POST"])
@auth_manager.require_auth
def rename_spreadsheet():
    """Rename a spreadsheet in user's list."""
    spreadsheet_id = request.json.get("spreadsheet_id", "").strip()
    new_name_raw = request.json.get("new_name", "")
    new_name_stripped = new_name_raw.strip()
    new_name = new_name_stripped if new_name_stripped else None

    if not spreadsheet_id:
        return jsonify({"success": False, "error": "Spreadsheet ID is required"})

    try:
        user = auth_manager.user

        success = user.rename_spreadsheet(spreadsheet_id, new_name)

        if success:
            return jsonify({"success": True, "message": "Spreadsheet renamed successfully"})
        else:
            return jsonify({"success": False, "error": "Spreadsheet not found in user's list"})

    except Exception as e:
        return jsonify({"success": False, "error": f"Error renaming spreadsheet: {e!s}"})


@settings_bp.route("/settings/remove-spreadsheet", methods=["POST"])
@auth_manager.require_auth
def remove_spreadsheet():
    """Remove a spreadsheet from user's list."""
    spreadsheet_id = request.json.get("spreadsheet_id", "").strip()

    if not spreadsheet_id:
        return jsonify({"success": False, "error": "Spreadsheet ID is required"})

    try:
        user = auth_manager.user

        # Remove the spreadsheet
        success = user.remove_spreadsheet(spreadsheet_id)

        if success:
            return jsonify({"success": True, "message": "Spreadsheet removed successfully"})
        else:
            return jsonify({"success": False, "error": "Spreadsheet not found in user's list"})

    except Exception as e:
        return jsonify({"success": False, "error": f"Error removing spreadsheet: {e!s}"})
