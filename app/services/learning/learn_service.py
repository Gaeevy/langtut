"""Learn mode service - orchestrates learn session logic.

This service encapsulates all business logic for learn (study) mode sessions,
including session initialization, answer processing, and results calculation.
"""

import logging
from dataclasses import dataclass

from app.config import config
from app.gsheet import read_card_set, update_spreadsheet
from app.models import Card
from app.services.auth_manager import auth_manager
from app.session_manager import SessionKeys as sk
from app.session_manager import SessionManager as sm
from app.utils import parse_timestamp

from .card_session import CardSessionManager
from .statistics import CardStatistics

logger = logging.getLogger(__name__)


@dataclass
class LearnSessionResult:
    """Result of initializing a learn session."""

    success: bool
    card_count: int = 0
    error: str | None = None


@dataclass
class CardDisplayContext:
    """Context for displaying a card in learn mode."""

    card: dict
    index: int
    total: int
    is_reviewing_incorrect: bool
    active_tab: str
    sheet_gid: int
    mode: str = "learn"


@dataclass
class AnswerProcessResult:
    """Result of processing an answer."""

    success: bool
    is_correct: bool = False
    level_change: dict | None = None
    error: str | None = None


@dataclass
class SessionEndResult:
    """Result of ending a learn session."""

    total_answered: int
    correct_answers: int
    accuracy_percentage: int
    review_count: int
    first_attempt_count: int
    answers: list
    original_count: int
    update_successful: bool
    ended_early: bool = False
    cards_remaining: int = 0


class LearnService:
    """Service for learn mode operations.

    Handles the complete learn session lifecycle:
    - Starting sessions with filtered cards
    - Displaying cards (including incorrect card review)
    - Processing answers and updating statistics
    - Ending sessions and persisting results
    """

    def __init__(self):
        """Initialize the learn service."""
        self.session = CardSessionManager("learn")
        self.stats = CardStatistics()

    def start_session(self, tab_name: str, spreadsheet_id: str) -> LearnSessionResult:
        """Start a new learn session.

        Args:
            tab_name: Name of the worksheet/tab to learn from
            spreadsheet_id: Google Sheets spreadsheet ID

        Returns:
            LearnSessionResult with success status and card count
        """
        try:
            # Read card set from Google Sheets
            card_set = read_card_set(worksheet_name=tab_name, spreadsheet_id=spreadsheet_id)

            if not card_set:
                return LearnSessionResult(success=False, error=f"Card set '{tab_name}' not found")

            # Get cards due for review
            cards = card_set.get_cards_to_review(
                limit=config.max_cards_per_session,
                ignore_unshown=False,
            )

            if not cards:
                return LearnSessionResult(success=False, error="No cards due for review")

            # Initialize session with cards
            self.session.initialize(cards, tab_name, card_set.gid)

            # Initialize learn-specific state
            sm.set(sk.LEARNING_ANSWERS, [])
            sm.set(sk.LEARNING_INCORRECT_CARDS, [])
            sm.set(sk.LEARNING_REVIEWING_INCORRECT, False)
            sm.set(sk.LEARNING_ORIGINAL_COUNT, len(cards))

            logger.info(f"Learn session started: {len(cards)} cards from '{tab_name}'")

            return LearnSessionResult(success=True, card_count=len(cards))

        except Exception as e:
            logger.error(f"Error starting learn session: {e}", exc_info=True)
            return LearnSessionResult(success=False, error=str(e))

    def get_current_card_context(self) -> CardDisplayContext | None:
        """Get context for displaying the current card.

        Handles the state machine for learn mode:
        1. Show cards from main list
        2. When done, switch to reviewing incorrect cards
        3. When review done, return None (session complete)

        Returns:
            CardDisplayContext for template rendering, or None if session complete
        """
        state = self.session.get_state()
        if not state:
            return None

        reviewing = sm.get(sk.LEARNING_REVIEWING_INCORRECT, False)
        index = state.current_index
        cards = state.cards

        # Check if we've completed the initial pass
        if index >= len(cards) and not reviewing:
            incorrect_cards = sm.get(sk.LEARNING_INCORRECT_CARDS, [])
            if incorrect_cards:
                # Start reviewing incorrect cards
                sm.set(sk.LEARNING_REVIEWING_INCORRECT, True)
                sm.set(sk.LEARNING_CURRENT_INDEX, 0)
                logger.info(f"Starting incorrect card review: {len(incorrect_cards)} cards")
                return self.get_current_card_context()  # Recursive call with new state
            return None  # Session complete

        # Check if we've completed reviewing incorrect cards
        if reviewing:
            incorrect_indices = sm.get(sk.LEARNING_INCORRECT_CARDS, [])
            if index >= len(incorrect_indices):
                return None  # Review complete

            # Get card from incorrect list
            card_index = incorrect_indices[index]
            card = cards[card_index].copy()
            card["is_review"] = True
            total = len(incorrect_indices)
        else:
            # Normal card from main list
            card = cards[index].copy()
            card["is_review"] = False
            total = len(cards)

        return CardDisplayContext(
            card=card,
            index=index,
            total=total,
            is_reviewing_incorrect=reviewing,
            active_tab=state.active_tab,
            sheet_gid=state.sheet_gid,
        )

    def process_answer(self, user_answer: str) -> AnswerProcessResult:
        """Process the user's answer.

        Updates card statistics and tracks incorrect answers for review.

        Args:
            user_answer: The answer submitted by the user

        Returns:
            AnswerProcessResult with correctness and level change info
        """
        context = self.get_current_card_context()
        if not context:
            return AnswerProcessResult(success=False, error="No active session")

        card = context.card
        reviewing = context.is_reviewing_incorrect

        # Check answer
        is_correct = self.stats.check_answer(user_answer, card["word"])

        # Determine the actual card index in the cards list
        if reviewing:
            incorrect_indices = sm.get(sk.LEARNING_INCORRECT_CARDS, [])
            card_index = incorrect_indices[context.index]
        else:
            card_index = context.index

        # Update card statistics
        card_obj = Card(**card)
        result = self.stats.update_on_answer(card_obj, is_correct)
        updated_card = result.updated_card
        level_change = result.level_change

        # Save updated card to session
        self.session.update_card(card_index, self.session._serialize_card(updated_card))

        # Record answer for results
        answer_record = self.stats.create_answer_record(
            card=card,
            user_answer=user_answer,
            is_correct=is_correct,
            is_review=reviewing,
            card_index=card_index,
        )
        answers = sm.get(sk.LEARNING_ANSWERS, [])
        answers.append(answer_record)
        sm.set(sk.LEARNING_ANSWERS, answers)

        # Track incorrect for later review (only on first pass)
        if not is_correct and not reviewing:
            incorrect = sm.get(sk.LEARNING_INCORRECT_CARDS, [])
            incorrect.append(context.index)
            sm.set(sk.LEARNING_INCORRECT_CARDS, incorrect)
            logger.info(f"Card marked for review. Total incorrect: {len(incorrect)}")

        # Store level change for feedback display
        sm.set(sk.LEARNING_LAST_LEVEL_CHANGE, level_change.to_dict())

        return AnswerProcessResult(
            success=True,
            is_correct=is_correct,
            level_change=level_change.to_dict(),
        )

    def get_level_change(self) -> dict | None:
        """Get and clear the last level change info.

        Returns:
            Level change dict or None if not set
        """
        level_change = sm.get(sk.LEARNING_LAST_LEVEL_CHANGE)
        if level_change:
            sm.remove(sk.LEARNING_LAST_LEVEL_CHANGE)
        return level_change

    def advance_to_next(self) -> None:
        """Advance to the next card."""
        index = sm.get(sk.LEARNING_CURRENT_INDEX, 0)
        sm.set(sk.LEARNING_CURRENT_INDEX, index + 1)

    def end_session(self, early: bool = False) -> SessionEndResult:
        """End the learn session and return results.

        Performs batch update to Google Sheets and clears session.

        Args:
            early: Whether the session is ending early (before completion)

        Returns:
            SessionEndResult with statistics and update status
        """
        answers = sm.get(sk.LEARNING_ANSWERS, [])
        original_count = sm.get(sk.LEARNING_ORIGINAL_COUNT, len(answers))

        # Calculate statistics
        stats = self.stats.calculate_session_stats(answers)

        # Batch update cards to spreadsheet
        update_successful = self._batch_update_cards()

        # Calculate remaining cards if ending early
        cards_remaining = 0
        if early:
            cards_remaining = original_count - stats.total_answered

        # Clear session
        sm.clear_namespace("learning")
        logger.info("Learn session ended, data cleared")

        return SessionEndResult(
            total_answered=stats.total_answered,
            correct_answers=stats.correct_answers,
            accuracy_percentage=stats.accuracy_percentage,
            review_count=stats.review_count,
            first_attempt_count=stats.first_attempt_count,
            answers=answers,
            original_count=original_count,
            update_successful=update_successful,
            ended_early=early,
            cards_remaining=cards_remaining,
        )

    def has_active_session(self) -> bool:
        """Check if there's an active learn session.

        Returns:
            True if session exists
        """
        return self.session.has_active_session()

    def _batch_update_cards(self) -> bool:
        """Batch update modified cards to Google Sheets.

        Returns:
            True if update successful, False otherwise
        """
        try:
            cards_data = sm.get(sk.LEARNING_CARDS, [])
            active_tab = sm.get(sk.LEARNING_ACTIVE_TAB)
            user = auth_manager.user
            user_spreadsheet_id = user.get_active_spreadsheet_id() if user else None

            if not cards_data or not active_tab or not user_spreadsheet_id:
                logger.warning("Missing session data for batch update")
                return False

            # Convert card dicts back to Card objects
            cards_to_update = []
            for card_data in cards_data:
                try:
                    card_data_copy = card_data.copy()
                    if card_data_copy.get("last_shown"):
                        card_data_copy["last_shown"] = parse_timestamp(card_data_copy["last_shown"])
                    card = Card(**card_data_copy)
                    cards_to_update.append(card)
                except Exception as e:
                    logger.error(f"Error converting card data: {e}")
                    continue

            if not cards_to_update:
                logger.warning("No valid cards to update")
                return False

            logger.info(f"Batch updating {len(cards_to_update)} cards to spreadsheet")

            update_spreadsheet(active_tab, cards_to_update, spreadsheet_id=user_spreadsheet_id)
            logger.info("✅ Batch spreadsheet update completed")
            return True

        except Exception as e:
            logger.error(f"❌ Error in batch update: {e}", exc_info=True)
            return False
