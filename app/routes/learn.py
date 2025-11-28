"""Learn mode routes for the Language Learning Flashcard App.

Handles the interactive study/learn session functionality.
Thin route handlers that delegate to LearnService.
"""

import logging

from flask import Blueprint, redirect, render_template, request, url_for

from app.services.auth_manager import auth_manager
from app.services.learning.learn_service import LearnService

logger = logging.getLogger(__name__)

# Create blueprint
learn_bp = Blueprint("learn", __name__, url_prefix="/learn")


@learn_bp.route("/start/<tab_name>", methods=["POST"])
@auth_manager.require_auth
def start(tab_name: str):
    """Start a learn session with cards from the specified tab."""
    logger.info(f"Starting learn session: {tab_name}")

    user = auth_manager.user
    spreadsheet_id = user.get_active_spreadsheet_id()

    service = LearnService()
    result = service.start_session(tab_name, spreadsheet_id)

    if not result.success:
        logger.warning(f"Failed to start learn session: {result.error}")
        return redirect(url_for("index.home"))

    logger.info(f"Learn session started with {result.card_count} cards")
    return redirect(url_for("learn.card"))


@learn_bp.route("/card")
@auth_manager.require_auth
def card():
    """Display the current flashcard."""
    service = LearnService()
    context = service.get_current_card_context()

    if not context:
        logger.info("No more cards, redirecting to results")
        return redirect(url_for("learn.results"))

    user = auth_manager.user

    return render_template(
        "card.html",
        card=context.card,
        index=context.index,
        total=context.total,
        reviewing=context.is_reviewing_incorrect,
        mode="learn",
        user_spreadsheet_id=user.get_active_spreadsheet_id(),
        active_tab=context.active_tab,
        sheet_gid=context.sheet_gid,
    )


@learn_bp.route("/answer", methods=["POST"])
@auth_manager.require_auth
def answer():
    """Process the user's answer to a flashcard."""
    user_answer = request.form.get("user_answer", "").strip()
    logger.info(f'User submitted answer: "{user_answer}"')

    service = LearnService()
    result = service.process_answer(user_answer)

    if not result.success:
        logger.warning(f"Answer processing failed: {result.error}")
        return redirect(url_for("index.home"))

    feedback_url = url_for("learn.feedback", correct="yes" if result.is_correct else "no")
    return redirect(feedback_url)


@learn_bp.route("/feedback/<correct>")
@auth_manager.require_auth
def feedback(correct: str):
    """Show feedback after answering a card."""
    service = LearnService()
    context = service.get_current_card_context()

    if not context:
        return redirect(url_for("index.home"))

    # Get level change info
    level_change = service.get_level_change()

    user = auth_manager.user

    return render_template(
        "feedback.html",
        card=context.card,
        index=context.index,
        total=context.total,
        correct=(correct == "yes"),
        user_answer=request.args.get("answer", ""),
        reviewing=context.is_reviewing_incorrect,
        card_index=context.index,
        level_change=level_change,
        mode="learn",
        user_spreadsheet_id=user.get_active_spreadsheet_id(),
        active_tab=context.active_tab,
        sheet_gid=context.sheet_gid,
    )


@learn_bp.route("/rate/<int:card_index>/<difficulty>")
@auth_manager.require_auth
def rate_difficulty(card_index: int, difficulty: str):
    """Rate the difficulty of a card (for future spaced repetition)."""
    logger.info(f"Card {card_index} rated as {difficulty}")
    return redirect(url_for("learn.next"))


@learn_bp.route("/next")
@auth_manager.require_auth
def next_card():
    """Move to the next card in the session."""
    service = LearnService()
    service.advance_to_next()
    return redirect(url_for("learn.card"))


@learn_bp.route("/results")
@auth_manager.require_auth
def results():
    """Display the results of the learning session."""
    service = LearnService()

    # Check if there's an active session
    if not service.has_active_session():
        return redirect(url_for("index.home"))

    result = service.end_session(early=False)

    return render_template(
        "results.html",
        total=result.total_answered,
        correct=result.correct_answers,
        percentage=result.accuracy_percentage,
        review_count=result.review_count,
        first_attempt_count=result.first_attempt_count,
        answers=result.answers,
        original_count=result.original_count,
        is_authenticated=True,
        updated=result.update_successful,
    )


@learn_bp.route("/end")
@auth_manager.require_auth
def end_early():
    """End the current learning session early."""
    service = LearnService()

    # Check if there's an active session
    if not service.has_active_session():
        return redirect(url_for("index.home"))

    result = service.end_session(early=True)

    return render_template(
        "results.html",
        total=result.total_answered,
        correct=result.correct_answers,
        percentage=result.accuracy_percentage,
        review_count=result.review_count,
        first_attempt_count=result.first_attempt_count,
        answers=result.answers,
        original_count=result.original_count,
        ended_early=True,
        cards_remaining=result.cards_remaining,
        is_authenticated=True,
        updated=result.update_successful,
    )
