"""
Flashcard routes for the Language Learning Flashcard App.

LEGACY MODULE - Routes are being migrated to dedicated blueprints:
- Homepage → routes/index.py (index_bp)
- Learn mode → routes/learn.py (learn_bp)
- Review mode → routes/review.py (coming in Phase 3)

This module provides backward-compatible redirects and review mode functionality.
"""

import logging

from flask import Blueprint, redirect, render_template, request, url_for

from src.gsheet import read_card_set
from src.services.auth_manager import auth_manager
from src.session_manager import SessionKeys as sk
from src.session_manager import SessionManager as sm
from src.utils import format_timestamp

# Create logger
logger = logging.getLogger(__name__)

# Create blueprint
flashcard_bp = Blueprint("flashcard", __name__)


# =============================================================================
# LEGACY REDIRECTS - These routes redirect to new blueprints
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
    return redirect(url_for("learn.start", tab_name=tab_name), code=307)  # 307 preserves POST


@flashcard_bp.route("/review/<tab_name>")
@auth_manager.require_auth
def start_review(tab_name: str):
    """Start a review session with ALL cards from the specified tab."""
    logger.info(f"Starting review session: {tab_name}")
    logger.info(f"Remote addr: {request.remote_addr}")

    # Get user's active spreadsheet
    user = auth_manager.user
    user_spreadsheet_id = user.get_active_spreadsheet_id() if user else None
    logger.info(f"User spreadsheet ID: {user_spreadsheet_id}")

    try:
        # Read ALL cards from the specified tab (no filtering)
        card_set = read_card_set(worksheet_name=tab_name, spreadsheet_id=user_spreadsheet_id)
        cards = card_set.cards  # Get all cards, not just cards_to_review

        logger.info(f'Loaded {len(cards)} cards from tab "{tab_name}" for review')

        # Log card details
        for i, card in enumerate(cards[:3]):  # Log first 3 cards
            logger.info(
                f"  Card {i + 1}: {card.word} -> {card.translation} (Level {card.level.value})"
            )
        if len(cards) > 3:
            logger.info(f"  ... and {len(cards) - 3} more cards")

        # Store cards in session (converted to dict for JSON serialization)
        cards_data = []
        for card in cards:
            card_dict = card.model_dump()
            card_dict["last_shown"] = format_timestamp(card.last_shown)
            cards_data.append(card_dict)

        sm.set(sk.REVIEW_CARDS, cards_data)
        sm.set(sk.REVIEW_CURRENT_INDEX, 0)
        sm.set(sk.REVIEW_ACTIVE_TAB, tab_name)
        sm.set(sk.REVIEW_SHEET_GID, card_set.gid)

        logger.info(f"Review session initialized: {len(cards)} cards, starting at index 0")
        logger.info(f"Active review tab set to: {tab_name}")

    except Exception as e:
        logger.error(f'Error starting review session for tab "{tab_name}": {e}')
        return redirect(url_for("index.home"))

    # Redirect to the first card in review mode
    return redirect(url_for("flashcard.show_card", mode="review"))


@flashcard_bp.route("/review/nav/<direction>")
@auth_manager.require_auth
def navigate_review(direction: str):
    """Navigate between cards in review mode with wraparound."""
    logger.info(f"=== REVIEW NAVIGATION: {direction} ===")

    if not sm.has(sk.REVIEW_CARDS) or not sm.has(sk.REVIEW_CURRENT_INDEX):
        logger.warning("Review cards or current_index not in session, redirecting to index")
        return redirect(url_for("index.home"))

    cards = sm.get(sk.REVIEW_CARDS)
    current_index = sm.get(sk.REVIEW_CURRENT_INDEX)
    total_cards = len(cards)

    if direction == "next":
        new_index = (current_index + 1) % total_cards  # Wraparound to 0 after last card
    elif direction == "prev":
        new_index = (current_index - 1) % total_cards  # Wraparound to last card before first
    else:
        logger.error(f"Invalid navigation direction: {direction}")
        return redirect(url_for("flashcard.show_card", mode="review"))

    sm.set(sk.REVIEW_CURRENT_INDEX, new_index)
    logger.info(f"Review navigation: {current_index} -> {new_index} ({direction})")

    return redirect(url_for("flashcard.show_card", mode="review"))


@flashcard_bp.route("/card")
@flashcard_bp.route("/card/<mode>")
@auth_manager.require_auth
def show_card(mode="study"):
    """Display the current flashcard.

    For study mode: redirects to learn.card
    For review mode: handles directly (will be migrated in Phase 3)
    """
    if mode != "review":
        # Redirect study mode to new learn blueprint
        logger.info("Legacy /card -> redirecting to learn.card")
        return redirect(url_for("learn.card"))

    # Review mode: keep existing logic until Phase 3
    logger.debug(f"Showing card - mode: {mode}")

    cards_key = sk.REVIEW_CARDS
    index_key = sk.REVIEW_CURRENT_INDEX
    tab_key = sk.REVIEW_ACTIVE_TAB
    gid_key = sk.REVIEW_SHEET_GID

    if not sm.has(cards_key) or not sm.has(index_key):
        logger.warning("Review cards not in session, redirecting to index")
        return redirect(url_for("index.home"))

    cards = sm.get(cards_key)
    index = sm.get(index_key)

    if index >= len(cards):
        logger.warning(f"Review index {index} out of bounds, resetting to 0")
        sm.set(index_key, 0)
        index = 0

    current_card = cards[index]
    current_card["is_review"] = False

    logger.info(f"Showing review card {index + 1}/{len(cards)}: {current_card['word']}")

    user = auth_manager.user
    user_spreadsheet_id = user.get_active_spreadsheet_id() if user else None

    return render_template(
        "card.html",
        card=current_card,
        index=index,
        total=len(cards),
        reviewing=False,
        mode=mode,
        user_spreadsheet_id=user_spreadsheet_id,
        active_tab=sm.get(tab_key, "Sheet1"),
        sheet_gid=sm.get(gid_key),
    )


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
def show_feedback_with_mode(correct: str, mode: str = "study"):
    """Show feedback - learn mode redirects, review mode handled here.

    Will be migrated in Phase 3.
    """
    if mode != "review":
        return redirect(url_for("learn.feedback", correct=correct))

    # Review mode: keep existing logic until Phase 3
    user = auth_manager.user
    user_spreadsheet_id = user.get_active_spreadsheet_id() if user else None

    cards_key = sk.REVIEW_CARDS
    index_key = sk.REVIEW_CURRENT_INDEX
    tab_key = sk.REVIEW_ACTIVE_TAB
    gid_key = sk.REVIEW_SHEET_GID

    if not sm.has(cards_key) or not sm.has(index_key):
        return redirect(url_for("index.home"))

    cards = sm.get(cards_key)
    index = sm.get(index_key)
    current_card = cards[index]

    return render_template(
        "feedback.html",
        card=current_card,
        index=index,
        total=len(cards),
        correct=True,
        user_answer="",
        reviewing=False,
        card_index=index,
        level_change=None,
        mode=mode,
        user_spreadsheet_id=user_spreadsheet_id,
        active_tab=sm.get(tab_key, "Sheet1"),
        sheet_gid=sm.get(gid_key),
    )


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
