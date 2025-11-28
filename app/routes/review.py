"""Review mode routes for the Language Learning Flashcard App.

Handles the card browsing/review functionality.
Thin route handlers that delegate to ReviewService.
"""

import logging

from flask import Blueprint, redirect, render_template, url_for

from app.services.auth_manager import auth_manager
from app.services.learning.review_service import ReviewService

logger = logging.getLogger(__name__)

# Create blueprint
review_bp = Blueprint("review", __name__, url_prefix="/review")


@review_bp.route("/start/<tab_name>")
@auth_manager.require_auth
def start(tab_name: str):
    """Start a review session with ALL cards from the specified tab."""
    logger.info(f"Starting review session: {tab_name}")

    user = auth_manager.user
    spreadsheet_id = user.get_active_spreadsheet_id()

    service = ReviewService()
    result = service.start_session(tab_name, spreadsheet_id)

    if not result.success:
        logger.warning(f"Failed to start review session: {result.error}")
        return redirect(url_for("index.home"))

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
    )


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


@review_bp.route("/end")
@auth_manager.require_auth
def end():
    """End the review session."""
    service = ReviewService()
    service.end_session()
    return redirect(url_for("index.home"))
