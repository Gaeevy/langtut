"""Irregular verbs routes."""

import logging

from flask import Blueprint, redirect, render_template, request, url_for

from app.services.auth_manager import auth_manager
from app.services.verbs_service import VerbsService

logger = logging.getLogger(__name__)

verbs_bp = Blueprint("verbs", __name__, url_prefix="/verbs")


@verbs_bp.route("")
@auth_manager.require_auth
def index():
    """Display irregular verbs overview with tense selector."""
    user = auth_manager.user
    if not user:
        return redirect(url_for("auth.auth"))

    service = VerbsService()
    tenses = service.list_tenses_simple()

    selected_tense_id = request.args.get("tense_id", type=int)
    if not selected_tense_id and tenses:
        selected_tense_id = tenses[0]["id"]

    infinitives = (
        service.for_user(user.id).list_infinitives_for_tense(selected_tense_id)
        if selected_tense_id is not None
        else []
    )
    next_infinitive = (
        service.get_least_recently_shown_infinitive(
            user_id=user.id,
            tense_id=selected_tense_id,
        )
        if selected_tense_id is not None
        else None
    )

    return render_template(
        "verbs/index.html",
        tenses=tenses,
        selected_tense_id=selected_tense_id,
        infinitives=infinitives,
        next_infinitive=next_infinitive,
    )


@verbs_bp.route("/practice/<int:tense_id>/<int:infinitive_id>")
@auth_manager.require_auth
def practice(tense_id: int, infinitive_id: int):
    """Render interactive practice page."""
    service = VerbsService()
    context = service.get_practice_context(tense_id=tense_id, infinitive_id=infinitive_id)
    if not context:
        return redirect(url_for("verbs.index"))

    return render_template(
        "verbs/practice.html",
        context=context,
        person_order=[1, 2, 3, 4, 5],
        person_labels=context.person_labels,
        next_practice_url=url_for("verbs.practice_next", tense_id=tense_id),
    )


@verbs_bp.route("/practice/next")
@auth_manager.require_auth
def practice_next():
    """Redirect to least-recently-shown infinitive for the selected tense."""
    user = auth_manager.user
    if not user:
        return redirect(url_for("auth.auth"))

    tense_id = request.args.get("tense_id", type=int)
    if tense_id is None:
        return redirect(url_for("verbs.index"))

    service = VerbsService()
    next_infinitive = service.get_least_recently_shown_infinitive(
        user_id=user.id,
        tense_id=tense_id,
    )
    if not next_infinitive:
        return redirect(url_for("verbs.index", tense_id=tense_id))

    return redirect(
        url_for(
            "verbs.practice",
            tense_id=tense_id,
            infinitive_id=next_infinitive["id"],
        )
    )
