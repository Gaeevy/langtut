"""
Flashcard routes for the Language Learning Flashcard App.

LEGACY MODULE - All routes have been migrated to dedicated blueprints:
- Homepage → routes/index.py (index_bp)
- Learn mode → routes/learn.py (learn_bp)
- Review mode → routes/review.py (review_bp)

This module provides backward-compatible redirects only.
"""

import logging

from flask import Blueprint, redirect, url_for

from src.services.auth_manager import auth_manager

# Create logger
logger = logging.getLogger(__name__)

# Create blueprint
flashcard_bp = Blueprint("flashcard", __name__)


# =============================================================================
# LEGACY REDIRECTS - All routes redirect to new blueprints
# =============================================================================


@flashcard_bp.route("/")
def index():
    """Legacy route - redirects to new index blueprint."""
    return redirect(url_for("index.home"))


@flashcard_bp.route("/start/<tab_name>", methods=["POST"])
@auth_manager.require_auth
def start_learning(tab_name: str):
    """Legacy route - redirects to new learn blueprint."""
    logger.info(f"Legacy /start/{tab_name} -> redirecting to learn.start")
    return redirect(url_for("learn.start", tab_name=tab_name), code=307)


@flashcard_bp.route("/review/<tab_name>")
@auth_manager.require_auth
def start_review(tab_name: str):
    """Legacy route - redirects to new review blueprint."""
    logger.info(f"Legacy /review/{tab_name} -> redirecting to review.start")
    return redirect(url_for("review.start", tab_name=tab_name))


@flashcard_bp.route("/review/nav/<direction>")
@auth_manager.require_auth
def navigate_review(direction: str):
    """Legacy route - redirects to new review blueprint."""
    logger.info(f"Legacy /review/nav/{direction} -> redirecting to review.navigate")
    return redirect(url_for("review.navigate", direction=direction))


@flashcard_bp.route("/card")
@flashcard_bp.route("/card/<mode>")
@auth_manager.require_auth
def show_card(mode="learn"):
    """Legacy route - redirects to appropriate blueprint."""
    if mode == "review":
        logger.info("Legacy /card/review -> redirecting to review.card")
        return redirect(url_for("review.card"))
    logger.info("Legacy /card -> redirecting to learn.card")
    return redirect(url_for("learn.card"))


@flashcard_bp.route("/answer", methods=["POST"])
@auth_manager.require_auth
def process_answer():
    """Legacy route - redirects to new learn blueprint."""
    logger.info("Legacy /answer -> redirecting to learn.answer")
    return redirect(url_for("learn.answer"), code=307)  # 307 preserves POST


@flashcard_bp.route("/feedback/<correct>")
@auth_manager.require_auth
def show_feedback(correct: str):
    """Legacy route - redirects to new learn blueprint."""
    logger.info(f"Legacy /feedback/{correct} -> redirecting to learn.feedback")
    return redirect(url_for("learn.feedback", correct=correct))


@flashcard_bp.route("/feedback/<correct>/<mode>")
@auth_manager.require_auth
def show_feedback_with_mode(correct: str, mode: str = "learn"):
    """Legacy route - redirects to appropriate blueprint."""
    if mode == "review":
        logger.info("Legacy /feedback/review -> redirecting to review.flip")
        return redirect(url_for("review.flip"))
    return redirect(url_for("learn.feedback", correct=correct))


@flashcard_bp.route("/rate-difficulty/<int:card_index>/<difficulty>")
@auth_manager.require_auth
def rate_difficulty(card_index: int, difficulty: str):
    """Legacy route - redirects to new learn blueprint."""
    return redirect(url_for("learn.rate_difficulty", card_index=card_index, difficulty=difficulty))


@flashcard_bp.route("/next")
@auth_manager.require_auth
def next_card():
    """Legacy route - redirects to new learn blueprint."""
    return redirect(url_for("learn.next_card"))


@flashcard_bp.route("/results")
@auth_manager.require_auth
def show_results():
    """Legacy route - redirects to new learn blueprint."""
    return redirect(url_for("learn.results"))


@flashcard_bp.route("/end-session")
@auth_manager.require_auth
def end_session_early():
    """Legacy route - redirects to new learn blueprint."""
    return redirect(url_for("learn.end_early"))
