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
