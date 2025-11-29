"""
Settings routes for the Language Learning Flashcard App.

Handles user settings and spreadsheet configuration.
"""

from flask import Blueprint, jsonify, render_template, request

from app.gsheet import extract_spreadsheet_id, read_all_card_sets, validate_spreadsheet_access
from app.services.auth_manager import auth_manager

# Create blueprint
settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/settings")
@auth_manager.require_auth
def settings():
    """Display user settings page."""
    # Get current user and their active spreadsheet
    user = auth_manager.user

    active_spreadsheet = user.get_active_spreadsheet()
    current_spreadsheet_id = active_spreadsheet.spreadsheet_id if active_spreadsheet else None
    current_spreadsheet_name = active_spreadsheet.spreadsheet_name if active_spreadsheet else None

    spreadsheets = user.get_all_spreadsheets()

    return render_template(
        "settings.html",
        user=user,
        current_spreadsheet_id=current_spreadsheet_id,
        current_spreadsheet_name=current_spreadsheet_name,
        spreadsheets=spreadsheets,
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
            return jsonify({"success": True, "message": "Spreadsheet activated successfully"})
        else:
            return jsonify({"success": False, "error": "Spreadsheet not found in user's list"})

    except Exception as e:
        return jsonify({"success": False, "error": f"Error activating spreadsheet: {e!s}"})


@settings_bp.route("/settings/rename-spreadsheet", methods=["POST"])
@auth_manager.require_auth
def rename_spreadsheet():
    """Rename a spreadsheet in user's list."""
    spreadsheet_id = request.json.get("spreadsheet_id", "").strip()
    new_name = request.json.get("new_name", "").strip()

    if not spreadsheet_id:
        return jsonify({"success": False, "error": "Spreadsheet ID is required"})

    if not new_name:
        return jsonify({"success": False, "error": "New name is required"})

    try:
        user = auth_manager.user

        # Remove the spreadsheet
        success = user.rename_spreadsheet(spreadsheet_id, new_name)

        if success:
            return jsonify({"success": True, "message": "Spreadsheet renammed successfully"})
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
