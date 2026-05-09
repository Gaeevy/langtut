"""Irregular verbs API routes."""

from typing import Any

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from app.config import config
from app.import_verbs import upsert_from_import_payload
from app.models import VerbImportRequest
from app.services.auth_manager import auth_manager
from app.services.verbs_service import VerbsService

verbs_api_bp = Blueprint("verbs_api", __name__, url_prefix="/verbs")


def _has_import_api_key() -> bool:
    """Allow non-session imports when a configured API key matches."""
    configured_key = config.verbs_import_api_key.strip()
    if not configured_key:
        return False
    provided_key = request.headers.get("X-Import-Key", "").strip()
    return provided_key == configured_key


@verbs_api_bp.route("/forms", methods=["POST"])
def upsert_forms() -> tuple[dict[str, Any], int] | dict[str, Any]:
    """Create or update one irregular verb payload.

    Access policy:
    - any authenticated user OR
    - a valid X-Import-Key header
    """
    if not auth_manager.is_authenticated() and not _has_import_api_key():
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "JSON body is required"}), 400

    try:
        payload = VerbImportRequest(**data)
    except ValidationError as exc:
        return jsonify({"success": False, "error": "Invalid payload", "details": exc.errors()}), 400

    result = upsert_from_import_payload(payload)
    return jsonify({"success": True, **result})


@verbs_api_bp.route("/tenses", methods=["GET"])
@auth_manager.require_auth_api
def list_tenses() -> dict[str, Any]:
    """List available tenses with counts."""
    service = VerbsService()
    return jsonify({"success": True, "tenses": service.list_tenses()})


@verbs_api_bp.route("/progress", methods=["POST"])
@auth_manager.require_auth_api
def save_progress() -> tuple[dict[str, Any], int] | dict[str, Any]:
    """Persist completion timestamp for one infinitive+tense pair."""
    data = request.get_json() or {}
    infinitive_id = data.get("infinitive_id")
    tense_id = data.get("tense_id")
    completed = bool(data.get("completed"))

    if not isinstance(infinitive_id, int) or not isinstance(tense_id, int):
        return jsonify(
            {"success": False, "error": "infinitive_id and tense_id must be integers"}
        ), 400
    if not completed:
        return jsonify({"success": False, "error": "completed flag is required"}), 400

    service = VerbsService()
    context = service.get_practice_context(tense_id=tense_id, infinitive_id=infinitive_id)
    if not context:
        return jsonify({"success": False, "error": "Practice target not found"}), 404
    user = auth_manager.user
    if not user:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    service.mark_practice_completed(
        user_id=user.id,
        tense_id=tense_id,
        infinitive_id=infinitive_id,
    )
    next_item = service.get_least_recently_shown_infinitive(
        user_id=user.id,
        tense_id=tense_id,
    )

    return jsonify({"success": True, "next_infinitive_id": next_item["id"] if next_item else None})
