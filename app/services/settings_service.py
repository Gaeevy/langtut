"""Service layer for spreadsheet settings flows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.database import User, UserSpreadsheet
from app.gsheet import (
    extract_spreadsheet_id,
    read_all_card_sets,
    spreadsheet_editor_url,
    validate_spreadsheet_access,
)


@dataclass
class ServiceResponse:
    """Simple transport-friendly service response."""

    payload: dict[str, Any]
    status_code: int = 200


def spreadsheet_summary(user_spreadsheet: UserSpreadsheet) -> dict[str, Any]:
    """Build JSON-ready spreadsheet summary for the picker UI."""
    sid = user_spreadsheet.spreadsheet_id
    return {
        "spreadsheet_id": sid,
        "spreadsheet_name": user_spreadsheet.spreadsheet_name,
        "spreadsheet_url": user_spreadsheet.spreadsheet_url or spreadsheet_editor_url(sid),
        "is_active": user_spreadsheet.is_active,
    }


class SettingsService:
    """Business logic for spreadsheet management endpoints."""

    def validate_spreadsheet(self, user: User, spreadsheet_url: str) -> ServiceResponse:
        """Validate spreadsheet access and attach it to a user."""
        if not spreadsheet_url:
            return ServiceResponse({"success": False, "error": "Spreadsheet URL is required"})

        try:
            spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
            if not spreadsheet_id:
                return ServiceResponse({"success": False, "error": "Invalid spreadsheet URL"})

            spreadsheet_name = validate_spreadsheet_access(spreadsheet_id)
            card_sets = read_all_card_sets(spreadsheet_id)
            if not card_sets:
                return ServiceResponse(
                    {"success": False, "error": "No valid card sets found in the spreadsheet"}
                )

            user_spreadsheet = user.add_spreadsheet(
                spreadsheet_id, spreadsheet_url, spreadsheet_name
            )
            return ServiceResponse(
                {
                    "success": True,
                    "spreadsheet": spreadsheet_summary(user_spreadsheet),
                    "id": user_spreadsheet.id,
                    "spreadsheet_id": spreadsheet_id,
                    "spreadsheet_name": spreadsheet_name,
                    "card_sets": [
                        {"name": cs.name, "card_count": len(cs.cards)} for cs in card_sets
                    ],
                }
            )
        except Exception as e:
            return ServiceResponse(
                {"success": False, "error": f"Error validating spreadsheet: {e!s}"}
            )

    def set_spreadsheet(self, user: User, spreadsheet_id: str) -> ServiceResponse:
        """Set spreadsheet as active by ID for a user."""
        if not spreadsheet_id:
            return ServiceResponse({"success": False, "error": "Spreadsheet ID is required"})
        try:
            user_spreadsheet = user.add_spreadsheet(spreadsheet_id)
            if user_spreadsheet:
                return ServiceResponse({"success": True, "message": "Spreadsheet set successfully"})
            return ServiceResponse({"success": False, "error": "Failed to set spreadsheet"})
        except Exception as e:
            return ServiceResponse({"success": False, "error": f"Error setting spreadsheet: {e!s}"})

    def activate_spreadsheet(self, user: User, spreadsheet_id: str) -> ServiceResponse:
        """Activate one of user's existing spreadsheets."""
        if not spreadsheet_id:
            return ServiceResponse({"success": False, "error": "Spreadsheet ID is required"})
        try:
            spreadsheet = user.activate_spreadsheet(spreadsheet_id)
            if spreadsheet:
                return ServiceResponse(
                    {
                        "success": True,
                        "message": "Spreadsheet activated successfully",
                        "spreadsheet": spreadsheet_summary(spreadsheet),
                    }
                )
            return ServiceResponse(
                {"success": False, "error": "Spreadsheet not found in user's list"}
            )
        except Exception as e:
            return ServiceResponse(
                {"success": False, "error": f"Error activating spreadsheet: {e!s}"}
            )

    def rename_spreadsheet(
        self, user: User, spreadsheet_id: str, new_name: str | None
    ) -> ServiceResponse:
        """Rename spreadsheet label in user's list."""
        if not spreadsheet_id:
            return ServiceResponse({"success": False, "error": "Spreadsheet ID is required"})
        try:
            success = user.rename_spreadsheet(spreadsheet_id, new_name)
            if success:
                return ServiceResponse(
                    {"success": True, "message": "Spreadsheet renamed successfully"}
                )
            return ServiceResponse(
                {"success": False, "error": "Spreadsheet not found in user's list"}
            )
        except Exception as e:
            return ServiceResponse(
                {"success": False, "error": f"Error renaming spreadsheet: {e!s}"}
            )

    def remove_spreadsheet(self, user: User, spreadsheet_id: str) -> ServiceResponse:
        """Remove spreadsheet from user's list."""
        if not spreadsheet_id:
            return ServiceResponse({"success": False, "error": "Spreadsheet ID is required"})
        try:
            success = user.remove_spreadsheet(spreadsheet_id)
            if success:
                return ServiceResponse(
                    {"success": True, "message": "Spreadsheet removed successfully"}
                )
            return ServiceResponse(
                {"success": False, "error": "Spreadsheet not found in user's list"}
            )
        except Exception as e:
            return ServiceResponse(
                {"success": False, "error": f"Error removing spreadsheet: {e!s}"}
            )
