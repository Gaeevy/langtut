"""Review mode routes for the Language Learning Flashcard App.

Handles the card browsing/review functionality.
Thin route handlers that delegate to ReviewService.
"""

import logging

from flask import Blueprint, abort, redirect, render_template, request, url_for

from app.services.auth_manager import auth_manager
from app.services.learning.review_service import ReviewOutcome, ReviewService
from app.session_manager import SessionKeys, SessionManager

logger = logging.getLogger(__name__)

# Create blueprint
review_bp = Blueprint("review", __name__, url_prefix="/review")


@review_bp.route("/start/<tab_name>")
@auth_manager.require_auth
def start(tab_name: str):
    """Start a review session with ALL cards from the specified tab."""
    user = auth_manager.user
    spreadsheet_id = user.get_active_spreadsheet_id()

    service = ReviewService()
    result = service.start_session(tab_name, spreadsheet_id)

    if not result.success:
        logger.warning(f"Failed to start review session: {result.error}")
        return redirect(url_for("index.home"))

    # Set target language in session
    user_spreadsheet = user.get_active_spreadsheet()

    if user_spreadsheet:
        language_settings = user_spreadsheet.get_language_settings()
        target_lang = language_settings.get("target", "pt")  # Default to pt

        sm = SessionManager()
        sm.set(SessionKeys.TARGET_LANGUAGE, target_lang)

    logger.info(f"Review session started with {result.card_count} cards")
    return redirect(url_for("review.card"))


@review_bp.route("/card")
@auth_manager.require_auth
def card():
    """Display the current review card (front side)."""
    service = ReviewService()
    context = service.get_current_card_context()

    if not context:
        logger.warning("No review session, redirecting to home")
        return redirect(url_for("index.home"))

    user = auth_manager.user
    return render_template(
        "card.html",
        card=context.card,
        index=context.index,
        total=context.total,
        reviewing=False,  # This is for learn mode's incorrect review
        mode="review",
        user_spreadsheet_id=user.get_active_spreadsheet_id(),
        active_tab=context.active_tab,
        sheet_gid=context.sheet_gid,
        review_error=request.args.get("error"),
    )


@review_bp.route("/flip")
@auth_manager.require_auth
def flip():
    """Show the flipped card (back side with answer)."""
    service = ReviewService()
    context = service.get_current_card_context()

    if not context:
        return redirect(url_for("index.home"))

    user = auth_manager.user
    return render_template(
        "feedback.html",
        card=context.card,
        index=context.index,
        total=context.total,
        correct=True,  # Not relevant for review mode
        user_answer="",  # Not relevant for review mode
        reviewing=False,
        card_index=context.index,
        level_change=None,
        mode="review",
        user_spreadsheet_id=user.get_active_spreadsheet_id(),
        active_tab=context.active_tab,
        sheet_gid=context.sheet_gid,
        review_error=request.args.get("error"),
    )


@review_bp.route("/answer/<outcome>", methods=["POST"])
@auth_manager.require_auth
def answer(outcome: str):
    """Record whether the current card was remembered and advance the stack."""
    try:
        review_outcome = ReviewOutcome(outcome)
    except ValueError:
        abort(400)

    user = auth_manager.user
    service = ReviewService()
    result = service.record_review(
        outcome=review_outcome,
        spreadsheet_id=user.get_active_spreadsheet_id(),
    )

    if not result.success:
        logger.warning("Review answer was not saved: %s", result.error)
        return redirect(url_for("review.flip", error="Could not save review progress. Try again."))

    if result.completed:
        return redirect(url_for("index.home"))
    return redirect(url_for("review.card"))


@review_bp.route("/nav/<direction>")
@auth_manager.require_auth
def navigate(direction: str):
    """Navigate between cards with wraparound."""
    logger.debug(f"Review navigation: {direction}")

    service = ReviewService()
    success = service.navigate(direction)

    if not success:
        logger.warning("Navigation failed, redirecting to home")
        return redirect(url_for("index.home"))

    return redirect(url_for("review.card"))


@review_bp.route("/end", methods=["POST"])
@auth_manager.require_auth
def end():
    """Persist reviewed cards and end the session early."""
    user = auth_manager.user
    service = ReviewService()
    result = service.end_session_early(user.get_active_spreadsheet_id())
    if not result.success:
        logger.warning("Early review end was not saved: %s", result.error)
        return redirect(url_for("review.card", error="Could not save review progress. Try again."))
    return redirect(url_for("index.home"))
