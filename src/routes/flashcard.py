"""
Flashcard routes for the Language Learning Flashcard App.

Handles the core flashcard learning functionality.
"""

import json
import logging

from flask import Blueprint, redirect, render_template, request, session, url_for

from src.config import config
from src.gsheet import read_all_card_sets, read_card_set, update_spreadsheet
from src.models import Card
from src.services.auth_manager import auth_manager
from src.session_manager import SessionKeys as sk
from src.session_manager import SessionManager as sm
from src.user_manager import get_user_spreadsheet_id
from src.utils import format_timestamp, get_timestamp, parse_timestamp

# Create logger
logger = logging.getLogger(__name__)

# Create blueprint
flashcard_bp = Blueprint("flashcard", __name__)


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle datetime and Level objects."""

    def default(self, obj):
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        return super().default(obj)


def batch_update_session_cards():
    """
    Extract modified cards from session and batch update them to Google Sheets.

    Returns:
        bool: True if update was successful, False otherwise
    """
    try:
        # Get session data
        cards_data = sm.get(sk.LEARNING_CARDS, [])
        active_tab = sm.get(sk.LEARNING_ACTIVE_TAB)
        user_spreadsheet_id = get_user_spreadsheet_id(session)

        if not cards_data or not active_tab or not user_spreadsheet_id:
            logger.warning("Missing session data for batch update")
            return False

        # Convert card dictionaries back to Card objects
        cards_to_update = []
        for card_data in cards_data:
            try:
                # Parse the timestamp back from string format
                if card_data.get("last_shown"):
                    card_data["last_shown"] = parse_timestamp(card_data["last_shown"])

                card = Card(**card_data)
                cards_to_update.append(card)
            except Exception as e:
                logger.error(f"Error converting card data to Card object: {e}")
                continue

        if not cards_to_update:
            logger.warning("No valid cards to update")
            return False

        logger.info(f"Batch updating {len(cards_to_update)} cards to spreadsheet")
        logger.info(f"Worksheet: {active_tab}, Spreadsheet: {user_spreadsheet_id}")

        # Perform the batch update
        update_spreadsheet(active_tab, cards_to_update, spreadsheet_id=user_spreadsheet_id)
        logger.info("✅ Batch spreadsheet update completed successfully")
        return True

    except Exception as e:
        logger.error(f"❌ Error in batch spreadsheet update: {e}", exc_info=True)
        return False


@flashcard_bp.route("/")
def index():
    """Homepage - shows login or flashcard selection."""
    logger.debug("Loading index page")
    logger.info(f"User agent: {request.headers.get('User-Agent', 'Unknown')}")

    # Check if session is working
    if not sm.has(sk.TEST_SESSION):
        sm.set(sk.TEST_SESSION, "Session is working")

    # Check authentication status using AuthManager
    user_is_authenticated = auth_manager.is_authenticated()
    user_spreadsheet_id = get_user_spreadsheet_id(session)

    logger.info(f"Authentication status: {user_is_authenticated}")
    logger.info(f"User spreadsheet ID: {user_spreadsheet_id}")

    # If not authenticated, show login screen
    if not user_is_authenticated:
        logger.info("User not authenticated, showing login screen")
        return render_template("login.html")

    # If no spreadsheet set, show setup screen
    if not user_spreadsheet_id:
        logger.info("No spreadsheet configured, showing setup screen")
        return render_template("setup.html", is_authenticated=user_is_authenticated)

    # Normal app flow with user's spreadsheet
    try:
        card_sets = read_all_card_sets(user_spreadsheet_id)
        logger.info(f"Found {len(card_sets)} card sets in spreadsheet {user_spreadsheet_id}")
        for card_set in card_sets:
            logger.info(f"  - {card_set.name}: {card_set.card_count} cards")
    except Exception as e:
        logger.error(f"Error reading card sets from spreadsheet {user_spreadsheet_id}: {e}")
        card_sets = []

    return render_template(
        "index.html",
        is_authenticated=user_is_authenticated,
        tabs=card_sets,
        user_spreadsheet_id=user_spreadsheet_id,
    )


@flashcard_bp.route("/start/<tab_name>", methods=["POST"])
def start_learning(tab_name: str):
    """Start a learning session with cards from the specified tab."""
    logger.info(f"Starting learning session: {tab_name}")
    logger.info(f"Remote addr: {request.remote_addr}")

    # Get user's active spreadsheet
    user_spreadsheet_id = get_user_spreadsheet_id(session)
    logger.info(f"User spreadsheet ID: {user_spreadsheet_id}")

    try:
        # Read cards from the specified tab
        card_set = read_card_set(worksheet_name=tab_name, spreadsheet_id=user_spreadsheet_id)
        cards = card_set.get_cards_to_review(
            limit=config.max_cards_per_session, ignore_unshown=False
        )

        logger.info(f'Loaded {len(cards)} cards from tab "{tab_name}" for review')
        logger.info(f"Max cards per session: {config.max_cards_per_session}")

        # Log card details
        for i, card in enumerate(cards[:3]):  # Log first 3 cards
            logger.info(
                f"  Card {i + 1}: {card.word} -> {card.translation} (Level {card.level.value})"
            )
        if len(cards) > 3:
            logger.info(f"  ... and {len(cards) - 3} more cards")

        # Store cards in session (converted to dict for JSON serialization)
        # We need to format datetime objects to strings for JSON serialization
        cards_data = []
        for card in cards:
            card_dict = card.model_dump()
            card_dict["last_shown"] = format_timestamp(card.last_shown)
            cards_data.append(card_dict)

        sm.set(sk.LEARNING_CARDS, cards_data)
        sm.set(sk.LEARNING_CURRENT_INDEX, 0)
        sm.set(sk.LEARNING_ANSWERS, [])
        sm.set(sk.LEARNING_INCORRECT_CARDS, [])  # Track indices of incorrectly answered cards
        sm.set(
            sk.LEARNING_REVIEWING_INCORRECT, False
        )  # Flag to indicate if we're reviewing incorrect cards
        sm.set(sk.LEARNING_ACTIVE_TAB, tab_name)
        sm.set(sk.LEARNING_ORIGINAL_COUNT, len(cards))  # Store total card count for reference

        # Cache the sheet GID to avoid repeated API calls
        sm.set(sk.LEARNING_SHEET_GID, card_set.gid)
        logger.info(f"Cached sheet GID in session: {card_set.gid}")

        logger.info(f"Session initialized: {len(cards)} cards, starting at index 0")
        logger.info(f"Active tab set to: {tab_name}")

    except Exception as e:
        logger.error(f'Error starting learning session for tab "{tab_name}": {e}')
        return redirect(url_for("flashcard.index"))

    # Redirect to the first card
    return redirect(url_for("flashcard.show_card"))


@flashcard_bp.route("/review/<tab_name>")
def start_review(tab_name: str):
    """Start a review session with ALL cards from the specified tab."""
    logger.info(f"Starting review session: {tab_name}")
    logger.info(f"Remote addr: {request.remote_addr}")

    # Get user's active spreadsheet
    user_spreadsheet_id = get_user_spreadsheet_id(session)
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
        return redirect(url_for("flashcard.index"))

    # Redirect to the first card in review mode
    return redirect(url_for("flashcard.show_card", mode="review"))


@flashcard_bp.route("/review/nav/<direction>")
def navigate_review(direction: str):
    """Navigate between cards in review mode with wraparound."""
    logger.info(f"=== REVIEW NAVIGATION: {direction} ===")

    if not sm.has(sk.REVIEW_CARDS) or not sm.has(sk.REVIEW_CURRENT_INDEX):
        logger.warning("Review cards or current_index not in session, redirecting to index")
        return redirect(url_for("flashcard.index"))

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
def show_card(mode="study"):
    """Display the current flashcard."""
    logger.debug(f"Showing card - mode: {mode}")

    # Determine session keys based on mode
    if mode == "review":
        cards_key = sk.REVIEW_CARDS
        index_key = sk.REVIEW_CURRENT_INDEX
        tab_key = sk.REVIEW_ACTIVE_TAB
        gid_key = sk.REVIEW_SHEET_GID
    else:  # study mode
        cards_key = sk.LEARNING_CARDS
        index_key = sk.LEARNING_CURRENT_INDEX
        tab_key = sk.LEARNING_ACTIVE_TAB
        gid_key = sk.LEARNING_SHEET_GID

    if not sm.has(cards_key) or not sm.has(index_key):
        logger.warning(
            f"Cards or current_index not in session for {mode} mode, redirecting to index"
        )
        return redirect(url_for("flashcard.index"))

    cards = sm.get(cards_key)
    index = sm.get(index_key)

    # Review mode: simple navigation without complex logic
    if mode == "review":
        if index >= len(cards):
            logger.warning(f"Review index {index} out of bounds, resetting to 0")
            sm.set(index_key, 0)
            index = 0

        current_card = cards[index]
        current_card["is_review"] = False  # Not the same as study review mode

        logger.info(
            f"Showing review card {index + 1}/{len(cards)}: {current_card['word']} -> {current_card['translation']}"
        )

        user_spreadsheet_id = get_user_spreadsheet_id(session)
        active_tab = sm.get(tab_key, "Sheet1")
        sheet_gid = sm.get(gid_key)

        return render_template(
            "card.html",
            card=current_card,
            index=index,
            total=len(cards),
            reviewing=False,  # This is review mode, not study review
            mode=mode,
            user_spreadsheet_id=user_spreadsheet_id,
            active_tab=active_tab,
            sheet_gid=sheet_gid,
        )

    # Study mode: existing logic
    reviewing = sm.get(sk.LEARNING_REVIEWING_INCORRECT, False)

    logger.info(f"Current index: {index}, Total cards: {len(cards)}, Reviewing: {reviewing}")

    # Check if we've gone through all the initial cards
    if index >= len(cards) and not reviewing:
        # If we have incorrect cards, start reviewing them
        if sm.get(sk.LEARNING_INCORRECT_CARDS, []):
            sm.set(sk.LEARNING_REVIEWING_INCORRECT, True)
            sm.set(sk.LEARNING_CURRENT_INDEX, 0)
            logger.info(
                f"Starting review mode with {len(sm.get(sk.LEARNING_INCORRECT_CARDS))} incorrect cards"
            )
            return redirect(url_for("flashcard.show_card"))
        else:
            # All cards correct, go to results
            logger.info("All cards completed, redirecting to results")
            return redirect(url_for("flashcard.show_results"))

    # If we're reviewing and reached the end of incorrect cards, go to results
    if reviewing and index >= len(sm.get(sk.LEARNING_INCORRECT_CARDS)):
        logger.info("Review completed, redirecting to results")
        return redirect(url_for("flashcard.show_results"))

    # Get the current card (either from original list or from incorrect cards)
    if reviewing:
        # Get the incorrect card index from the stored list
        incorrect_idx = sm.get(sk.LEARNING_INCORRECT_CARDS)[index]
        current_card = cards[incorrect_idx]
        # Add a flag to indicate this is a review card
        current_card["is_review"] = True
        logger.info(
            f"Showing review card {index + 1}/{len(sm.get(sk.LEARNING_INCORRECT_CARDS))}: {current_card['word']} (original index {incorrect_idx})"
        )
    else:
        current_card = cards[index]
        current_card["is_review"] = False
        logger.info(
            f"Showing card {index + 1}/{len(cards)}: {current_card['word']} -> {current_card['translation']}"
        )

    user_spreadsheet_id = get_user_spreadsheet_id(session)
    active_tab = sm.get(sk.LEARNING_ACTIVE_TAB, "Sheet1")
    # Use cached sheet GID instead of making API call
    sheet_gid = sm.get(sk.LEARNING_SHEET_GID)

    logger.info(
        f"Template context: spreadsheet_id={user_spreadsheet_id}, tab={active_tab}, sheet_gid={sheet_gid} (cached)"
    )

    return render_template(
        "card.html",
        card=current_card,
        index=index,
        total=len(sm.get(sk.LEARNING_INCORRECT_CARDS)) if reviewing else len(cards),
        reviewing=reviewing,
        mode=mode,
        user_spreadsheet_id=user_spreadsheet_id,
        active_tab=active_tab,
        sheet_gid=sheet_gid,
    )


@flashcard_bp.route("/answer", methods=["POST"])
def process_answer():
    """Process the user's answer to a flashcard."""
    logger.debug("Processing answer")

    if not sm.has(sk.LEARNING_CARDS) or not sm.has(sk.LEARNING_CURRENT_INDEX):
        logger.warning("Cards or current_index not in session, redirecting to index")
        return redirect(url_for("flashcard.index"))

    # Get user's answer
    user_answer = request.form.get("user_answer", "").strip().lower()
    logger.info(f'User submitted answer: "{user_answer}"')

    # Check if we're in review mode
    reviewing = sm.get(sk.LEARNING_REVIEWING_INCORRECT, False)

    # Get current card
    cards = sm.get(sk.LEARNING_CARDS)
    index = sm.get(sk.LEARNING_CURRENT_INDEX)

    if reviewing:
        # Get the original index of the card being reviewed
        original_index = sm.get(sk.LEARNING_INCORRECT_CARDS)[index]
        current_card = cards[original_index]
        logger.info(
            f"Processing review answer for card {index + 1}/{len(sm.get(sk.LEARNING_INCORRECT_CARDS))} (original index {original_index})"
        )
    else:
        current_card = cards[index]
        logger.info(f"Processing initial answer for card {index + 1}/{len(cards)}")

    # Check answer (simple exact match for now)
    correct_answers = [current_card["word"].strip().lower()]  # User types Portuguese word

    # Check if answer is correct
    is_correct = user_answer in correct_answers
    logger.info(f"Answer correctness: {is_correct}")
    logger.info(f"Expected answers: {correct_answers}")

    # Store answer in session for results
    answers = sm.get(sk.LEARNING_ANSWERS, [])
    answer_data = {
        "card_index": original_index if reviewing else index,
        "word": current_card["word"],
        "translation": current_card["translation"],
        "user_answer": user_answer,
        "correct_answer": current_card["word"],
        "is_correct": is_correct,
        "timestamp": get_timestamp().isoformat(),
        "is_review": reviewing,
    }
    answers.append(answer_data)
    sm.set(sk.LEARNING_ANSWERS, answers)

    # Track incorrect answers for review
    if not is_correct and not reviewing:
        incorrect_cards = sm.get(sk.LEARNING_INCORRECT_CARDS, [])
        incorrect_cards.append(index)
        sm.set(sk.LEARNING_INCORRECT_CARDS, incorrect_cards)
        logger.info(f"Added card to incorrect list. Total incorrect cards: {len(incorrect_cards)}")

    # Update card statistics in session (no immediate spreadsheet write)
    try:
        # Create Card object from current card data
        card = Card(**current_card)

        # Store original level for comparison
        original_level = card.level.value

        # Update statistics
        card.cnt_shown += 1
        card.last_shown = get_timestamp()

        # Simple level progression: +1 for correct, -1 for incorrect
        if is_correct:
            card.cnt_corr_answers += 1
            # Always advance level for correct answers
            card.level = card.level.next_level()
            logger.info(
                f"✅ Correct answer! Card level advanced from {original_level} to {card.level.value}"
            )
        else:
            # Always decrease level for incorrect answers
            card.level = card.level.previous_level()
            logger.info(
                f"❌ Incorrect answer! Card level decreased from {original_level} to {card.level.value}"
            )

        # Update the session data with the new statistics
        cards = sm.get(sk.LEARNING_CARDS)
        card_dict = card.model_dump()
        card_dict["last_shown"] = format_timestamp(
            card.last_shown
        )  # Convert back to string for session

        if reviewing:
            cards[original_index] = card_dict
        else:
            cards[index] = card_dict
        sm.set(sk.LEARNING_CARDS, cards)
        logger.info(
            "✅ Session card statistics updated in memory (will batch update at session end)"
        )

        # Store level change information for the feedback page
        sm.set(
            sk.LEARNING_LAST_LEVEL_CHANGE,
            {
                "from": original_level,
                "to": card.level.value,
                "is_correct": is_correct,
            },
        )

    except Exception as e:
        logger.error(f"Error updating card statistics in session: {e}", exc_info=True)
        # Continue without showing error to user

    # Redirect to feedback page
    feedback_url = url_for("flashcard.show_feedback", correct="yes" if is_correct else "no")
    logger.info(f"Redirecting to feedback page: {feedback_url}")
    return redirect(feedback_url)


@flashcard_bp.route("/feedback/<correct>")
def show_feedback(correct: str):
    """Show feedback after answering a card."""
    return show_feedback_with_mode(correct, "study")


@flashcard_bp.route("/feedback/<correct>/<mode>")
def show_feedback_with_mode(correct: str, mode: str = "study"):
    """Show feedback after answering a card or flip view in review mode."""

    # Determine session keys based on mode
    if mode == "review":
        cards_key = sk.REVIEW_CARDS
        index_key = sk.REVIEW_CURRENT_INDEX
        tab_key = sk.REVIEW_ACTIVE_TAB
        gid_key = sk.REVIEW_SHEET_GID
    else:  # study mode
        cards_key = sk.LEARNING_CARDS
        index_key = sk.LEARNING_CURRENT_INDEX
        tab_key = sk.LEARNING_ACTIVE_TAB
        gid_key = sk.LEARNING_SHEET_GID

    if not sm.has(cards_key) or not sm.has(index_key):
        return redirect(url_for("flashcard.index"))

    cards = sm.get(cards_key)
    index = sm.get(index_key)

    # Review mode: simple card display
    if mode == "review":
        current_card = cards[index]

        return render_template(
            "feedback.html",
            card=current_card,
            index=index,
            total=len(cards),
            correct=True,  # Not relevant for review mode
            user_answer="",  # Not relevant for review mode
            reviewing=False,
            card_index=index,
            level_change=None,
            mode=mode,
            user_spreadsheet_id=get_user_spreadsheet_id(session),
            active_tab=sm.get(tab_key, "Sheet1"),
            sheet_gid=sm.get(gid_key),
        )

    # Study mode: existing logic
    reviewing = sm.get(sk.LEARNING_REVIEWING_INCORRECT, False)

    # Get the current card
    if reviewing:
        incorrect_idx = sm.get(sk.LEARNING_INCORRECT_CARDS)[index]
        current_card = cards[incorrect_idx]
    else:
        current_card = cards[index]

    # Get the last answer
    last_answer = sm.get(sk.LEARNING_ANSWERS, [])[-1] if sm.get(sk.LEARNING_ANSWERS) else None

    # Get level change information
    level_change = sm.get(sk.LEARNING_LAST_LEVEL_CHANGE)
    if level_change:
        sm.remove(sk.LEARNING_LAST_LEVEL_CHANGE)

    return render_template(
        "feedback.html",
        card=current_card,
        correct=(correct == "yes"),
        user_answer=last_answer["user_answer"] if last_answer else "",
        reviewing=reviewing,
        card_index=index,
        level_change=level_change,
        mode=mode,
        user_spreadsheet_id=get_user_spreadsheet_id(session),
        active_tab=sm.get(sk.LEARNING_ACTIVE_TAB, "Sheet1"),
        # Use cached sheet GID instead of making API call
        sheet_gid=sm.get(sk.LEARNING_SHEET_GID),
    )


@flashcard_bp.route("/rate-difficulty/<int:card_index>/<difficulty>")
def rate_difficulty(card_index: int, difficulty: str):
    """Rate the difficulty of a card (for future spaced repetition)."""
    # For now, just acknowledge the rating and continue
    # In the future, this could affect the spaced repetition algorithm
    logger.info(f"Card {card_index} rated as {difficulty}")
    return redirect(url_for("flashcard.next_card"))


@flashcard_bp.route("/next")
def next_card():
    """Move to the next card in the session."""
    if not sm.has(sk.LEARNING_CURRENT_INDEX):
        return redirect(url_for("flashcard.index"))

    current_index = sm.get(sk.LEARNING_CURRENT_INDEX)
    sm.set(sk.LEARNING_CURRENT_INDEX, current_index + 1)
    return redirect(url_for("flashcard.show_card"))


@flashcard_bp.route("/results")
def show_results():
    """Display the results of the learning session."""
    if not sm.has(sk.LEARNING_ANSWERS):
        return redirect(url_for("flashcard.index"))

    answers = sm.get(sk.LEARNING_ANSWERS, [])
    original_count = sm.get(sk.LEARNING_ORIGINAL_COUNT, len(answers))

    # Calculate statistics
    total_answered = len(answers)
    correct_answers = sum(1 for answer in answers if answer["is_correct"])

    # Calculate review statistics
    incorrect_cards = sm.get(sk.LEARNING_INCORRECT_CARDS, [])
    review_count = len([a for a in answers if a.get("card_index", 0) in incorrect_cards])
    first_attempt_count = total_answered - review_count

    # Calculate accuracy percentage
    accuracy = (correct_answers / total_answered * 100) if total_answered > 0 else 0

    # Batch update all modified cards to Google Sheets
    logger.info("🔄 Session completed - performing batch spreadsheet update...")
    update_successful = batch_update_session_cards()

    if update_successful:
        logger.info("✅ All card statistics successfully saved to spreadsheet")
    else:
        logger.warning("⚠️ Some card statistics may not have been saved")

    # Clear session data after successful update
    sm.clear_namespace("learning")
    logger.info("Learning session data cleared from memory")

    return render_template(
        "results.html",
        total=total_answered,
        correct=correct_answers,
        percentage=int(accuracy),
        review_count=review_count,
        first_attempt_count=first_attempt_count,
        answers=answers,
        original_count=original_count,
        is_authenticated=auth_manager.is_authenticated(),
        updated=update_successful,  # Now reflects actual update status
    )


@flashcard_bp.route("/end-session")
def end_session_early():
    """End the current learning session early."""
    # Calculate partial results
    answers = sm.get(sk.LEARNING_ANSWERS, [])
    original_count = sm.get(sk.LEARNING_ORIGINAL_COUNT, len(answers))

    total_answered = len(answers)
    correct_answers = sum(1 for answer in answers if answer["is_correct"])

    # Calculate review statistics
    incorrect_cards = sm.get(sk.LEARNING_INCORRECT_CARDS, [])
    review_count = len([a for a in answers if a.get("card_index", 0) in incorrect_cards])
    first_attempt_count = total_answered - review_count

    accuracy = (correct_answers / total_answered * 100) if total_answered > 0 else 0

    # Batch update all modified cards to Google Sheets before ending
    logger.info("🔄 Session ended early - performing batch spreadsheet update...")
    update_successful = batch_update_session_cards()

    if update_successful:
        logger.info("✅ All card statistics successfully saved to spreadsheet")
    else:
        logger.warning("⚠️ Some card statistics may not have been saved")

    # Clear session data after update attempt
    sm.clear_namespace("learning")
    logger.info("Learning session data cleared from memory")

    return render_template(
        "results.html",
        total=total_answered,
        correct=correct_answers,
        percentage=int(accuracy),
        review_count=review_count,
        first_attempt_count=first_attempt_count,
        answers=answers,
        original_count=original_count,
        ended_early=True,
        cards_remaining=original_count - total_answered,
        is_authenticated=auth_manager.is_authenticated(),
        updated=update_successful,  # Now reflects actual update status
    )
