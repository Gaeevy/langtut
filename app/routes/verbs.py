"""Irregular verbs routes."""

import logging

from flask import Blueprint, redirect, render_template, request, url_for

from app.services.auth_manager import auth_manager
from app.services.verbs_service import PERSON_LABELS, VerbsService

logger = logging.getLogger(__name__)

verbs_bp = Blueprint("verbs", __name__, url_prefix="/verbs")


@verbs_bp.route("")
@auth_manager.require_auth
def index():
    """Display irregular verbs overview with tense selector."""
    service = VerbsService()
    tenses = service.list_tenses()

    selected_tense_id = request.args.get("tense_id", type=int)
    if not selected_tense_id and tenses:
        selected_tense_id = tenses[0]["id"]

    infinitives = (
        service.list_infinitives_for_tense(selected_tense_id)
        if selected_tense_id is not None
        else []
    )

    return render_template(
        "verbs/index.html",
        tenses=tenses,
        selected_tense_id=selected_tense_id,
        infinitives=infinitives,
    )


@verbs_bp.route("/practice/<int:tense_id>/<int:infinitive_id>")
@auth_manager.require_auth
def practice(tense_id: int, infinitive_id: int):
    """Render verb practice page with five input fields."""
    service = VerbsService()
    context = service.get_practice_context(tense_id=tense_id, infinitive_id=infinitive_id)
    if not context:
        return redirect(url_for("verbs.index"))

    return render_template(
        "verbs/practice.html",
        context=context,
        person_order=[1, 2, 3, 4, 5],
        result=None,
        person_labels=PERSON_LABELS,
    )


@verbs_bp.route("/practice/<int:tense_id>/<int:infinitive_id>", methods=["POST"])
@auth_manager.require_auth
def submit_practice(tense_id: int, infinitive_id: int):
    """Validate submitted forms and render same page with feedback."""
    service = VerbsService()
    context = service.get_practice_context(tense_id=tense_id, infinitive_id=infinitive_id)
    if not context:
        return redirect(url_for("verbs.index"))

    submitted_forms = {
        person: request.form.get(f"form_{person}", "").strip() for person in PERSON_LABELS
    }
    result = service.check_answers(
        tense_id=tense_id,
        infinitive_id=infinitive_id,
        submitted_forms=submitted_forms,
    )
    if not result:
        return redirect(url_for("verbs.index"))

    return render_template(
        "verbs/practice.html",
        context=context,
        person_order=[1, 2, 3, 4, 5],
        result=result,
        person_labels=PERSON_LABELS,
    )
