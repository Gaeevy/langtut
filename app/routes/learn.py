"""Learn mode routes for the Language Learning Flashcard App.

Handles the interactive study/learn session functionality.
Thin route handlers that delegate to LearnService.
"""

import logging

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from app.services.auth_manager import auth_manager
from app.services.learning.learn_service import LearnService
from app.session_manager import SessionKeys, SessionManager

logger = logging.getLogger(__name__)

# Create blueprint
learn_bp = Blueprint("learn", __name__, url_prefix="/learn")


@learn_bp.route("/start/<tab_name>", methods=["POST"])
@auth_manager.require_auth
def start(tab_name: str):
    """Start learning session."""
    user = auth_manager.user
    spreadsheet_id = user.get_active_spreadsheet_id()

    service = LearnService()
    result = service.start_session(tab_name, spreadsheet_id)

    if not result.success:
        logger.warning(f"Failed to start learn session: {result.error}")
        return redirect(url_for("index.home"))

    user_spreadsheet = user.get_active_spreadsheet()
    if user_spreadsheet:
        language_settings = user_spreadsheet.get_language_settings()
        target_lang = language_settings.get("target", "pt")
        sm = SessionManager()
        sm.set(SessionKeys.TARGET_LANGUAGE, target_lang)

    logger.info(f"Learn session started: {result.card_count} cards, {result.task_count} tasks")
    return redirect(url_for("learn.card"))


@learn_bp.route("/card")
@auth_manager.require_auth
def card():
    """Display the current flashcard."""
    service = LearnService()
    context = service.get_current_card_context()

    if not context:
        logger.info("No more tasks, redirecting to results")
        return redirect(url_for("learn.results"))

    user = auth_manager.user

    return render_template(
        "card.html",
        card=context.card,
        task_index=context.task_index,
        task_total=context.task_total,
        progress_sections=context.progress_sections,
        initial_task_length=context.initial_task_length,
        reviewing=False,
        mode="learn",
        question_mode=context.mode,
        mode_data=context.mode_data,
        user_spreadsheet_id=user.get_active_spreadsheet_id(),
        active_tab=context.active_tab,
        sheet_gid=context.sheet_gid,
    )


@learn_bp.route("/answer", methods=["POST"])
@auth_manager.require_auth
def answer():
    """Process the user's answer to a flashcard.

    Supports both traditional form POST (redirect) and AJAX JSON requests
    (returns JSON for in-page feedback rendering with audio autoplay).
    """
    is_ajax = request.is_json

    if is_ajax:
        data = request.get_json()
        user_answer = data.get("user_answer", "").strip()
    else:
        user_answer = request.form.get("user_answer", "").strip()

    logger.info(f'User submitted answer: "{user_answer}"')

    service = LearnService()
    result = service.process_answer(user_answer)

    if not result.success:
        if is_ajax:
            return jsonify({"success": False, "error": result.error})
        logger.warning(f"Answer processing failed: {result.error}")
        return redirect(url_for("index.home"))

    if is_ajax:
        context = service.get_current_card_context()
        user = auth_manager.user

        card = context.card if context else {}
        level_val = card.get("level", 0)
        if hasattr(level_val, "value"):
            level_val = level_val.value

        progress_sections = context.progress_sections if context else []
        return jsonify(
            {
                "success": True,
                "correct": result.is_correct,
                "card": {
                    "word": card.get("word", ""),
                    "translation": card.get("translation", ""),
                    "example": card.get("example"),
                    "example_translation": card.get("example_translation"),
                    "level": level_val,
                },
                "question_mode": context.mode if context else "type_answer",
                "task_index": context.task_index if context else 0,
                "task_total": context.task_total if context else 0,
                "progress_sections": progress_sections,
                "spreadsheet_id": user.get_active_spreadsheet_id() if user else None,
                "sheet_gid": context.sheet_gid if context else None,
            }
        )

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

    user = auth_manager.user

    return render_template(
        "feedback.html",
        card=context.card,
        task_index=context.task_index,
        task_total=context.task_total,
        # kept for template compat with review mode
        index=context.task_index,
        total=context.task_total,
        correct=(correct == "yes"),
        reviewing=False,
        card_index=context.task_index,
        mode="learn",
        question_mode=context.mode,
        user_spreadsheet_id=user.get_active_spreadsheet_id(),
        active_tab=context.active_tab,
        sheet_gid=context.sheet_gid,
    )


@learn_bp.route("/rate/<int:card_index>/<difficulty>")
@auth_manager.require_auth
def rate_difficulty(card_index: int, difficulty: str):
    """Rate the difficulty of a card (stub for future spaced repetition)."""
    logger.info(f"Card {card_index} rated as {difficulty}")
    return redirect(url_for("learn.next_card"))


@learn_bp.route("/next_card")
@auth_manager.require_auth
def next_card():
    """Move to the next task in the session."""
    service = LearnService()
    service.advance_to_next()
    return redirect(url_for("learn.card"))


@learn_bp.route("/results")
@auth_manager.require_auth
def results():
    """Display the results of the learning session."""
    service = LearnService()

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
        tab_name=result.session_tab,
        per_card_breakdown=result.per_card_breakdown,
    )


@learn_bp.route("/end")
@auth_manager.require_auth
def end_early():
    """End the current learning session early."""
    service = LearnService()

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
        tab_name=result.session_tab,
        per_card_breakdown=result.per_card_breakdown,
    )
