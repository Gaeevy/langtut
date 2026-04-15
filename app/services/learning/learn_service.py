"""Learn mode service - orchestrates learn session logic.

This service encapsulates all business logic for learn (study) mode sessions,
including session initialization, answer processing, and results calculation.

The session is built as a task queue: an ordered list of {card_idx, mode} pairs.
Cards appear multiple times in the queue (once per mode in their pipeline).
A single task index walks the full queue, so progress is always linear.
"""

import logging
from dataclasses import dataclass, field

from app.config import config
from app.gsheet import read_card_set, update_spreadsheet
from app.models import Card
from app.services.auth_manager import auth_manager
from app.session_manager import SessionKeys as sk
from app.session_manager import SessionManager as sm
from app.utils import parse_timestamp

from .card_session import CardSessionManager
from .mode_config import (
    LearningMode,
    build_options,
    build_task_queue,
    shuffle_letters,
    shuffle_words,
)
from .statistics import CardStatistics

logger = logging.getLogger(__name__)


@dataclass
class LearnSessionResult:
    """Result of initializing a learn session."""

    success: bool
    card_count: int = 0
    task_count: int = 0
    error: str | None = None


@dataclass
class CardDisplayContext:
    """Context for displaying a card in learn mode."""

    card: dict
    index: int  # position within the current mode-round (for display)
    total: int  # total tasks in this mode-round (for display)
    task_index: int  # absolute position in the full task queue
    task_total: int  # total tasks in the queue
    is_reviewing_incorrect: bool
    active_tab: str
    sheet_gid: int
    mode: str = LearningMode.TYPE_ANSWER
    mode_data: dict = field(default_factory=dict)


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
    - Starting sessions with filtered cards (builds a task queue)
    - Displaying cards with mode-specific context
    - Processing answers with mode-aware checking
    - Ending sessions and persisting results
    """

    def __init__(self):
        """Initialize the learn service."""
        self.session = CardSessionManager("learn")
        self.stats = CardStatistics()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def start_session(self, tab_name: str, spreadsheet_id: str) -> LearnSessionResult:
        """Start a new learn session.

        Reads cards from the spreadsheet, builds a task queue based on each
        card's level pipeline, and initialises session state.

        Args:
            tab_name: Name of the worksheet/tab to learn from
            spreadsheet_id: Google Sheets spreadsheet ID

        Returns:
            LearnSessionResult with success status, card count, and task count
        """
        try:
            card_set = read_card_set(worksheet_name=tab_name, spreadsheet_id=spreadsheet_id)

            if not card_set:
                return LearnSessionResult(success=False, error=f"Card set '{tab_name}' not found")

            cards = card_set.get_cards_to_review(
                limit=config.max_cards_per_session,
                ignore_unshown=False,
            )

            if not cards:
                return LearnSessionResult(success=False, error="No cards due for review")

            # Store cards and build task queue
            self.session.initialize(cards, tab_name, card_set.gid)

            task_queue = build_task_queue(cards)
            sm.set(sk.LEARNING_TASK_QUEUE, task_queue)
            sm.set(sk.LEARNING_TASK_INDEX, 0)

            # Initialise answer tracking state
            sm.set(sk.LEARNING_ANSWERS, [])
            sm.set(sk.LEARNING_INCORRECT_CARDS, [])
            sm.set(sk.LEARNING_REVIEWING_INCORRECT, False)
            sm.set(sk.LEARNING_ORIGINAL_COUNT, len(cards))

            logger.info(
                f"Learn session started: {len(cards)} cards, {len(task_queue)} tasks from '{tab_name}'"
            )

            return LearnSessionResult(
                success=True,
                card_count=len(cards),
                task_count=len(task_queue),
            )

        except Exception as e:
            logger.error(f"Error starting learn session: {e}", exc_info=True)
            return LearnSessionResult(success=False, error=str(e))

    def has_active_session(self) -> bool:
        """Check if there's an active learn session."""
        return self.session.has_active_session()

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

        stats = self.stats.calculate_session_stats(answers)

        update_successful = self._batch_update_cards()

        cards_remaining = 0
        if early:
            task_queue = sm.get(sk.LEARNING_TASK_QUEUE, [])
            task_index = sm.get(sk.LEARNING_TASK_INDEX, 0)
            cards_remaining = len(task_queue) - task_index

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

    # ------------------------------------------------------------------
    # Card display
    # ------------------------------------------------------------------

    def get_current_card_context(self) -> CardDisplayContext | None:
        """Get context for displaying the current task (card + mode).

        Reads the current task from the task queue. Once the main queue is
        exhausted, switches to reviewing incorrect tasks. Returns None when
        fully complete.

        Returns:
            CardDisplayContext for template rendering, or None if session complete
        """
        session_state = self.session.get_state()
        if not session_state:
            return None

        reviewing = sm.get(sk.LEARNING_REVIEWING_INCORRECT, False)
        task_queue = sm.get(sk.LEARNING_TASK_QUEUE, [])
        task_index = sm.get(sk.LEARNING_TASK_INDEX, 0)

        if not reviewing:
            # Main pass
            if task_index >= len(task_queue):
                return self._start_review_pass_or_finish(session_state.cards)
            task = task_queue[task_index]
        else:
            # Review pass: incorrect tasks stored separately
            incorrect_tasks = sm.get(sk.LEARNING_INCORRECT_CARDS, [])
            if task_index >= len(incorrect_tasks):
                return None  # Review complete
            task = incorrect_tasks[task_index]

        card_idx = task["card_idx"]
        mode = task["mode"]
        card = session_state.cards[card_idx].copy()
        card["is_review"] = reviewing

        mode_data = self._build_mode_data(mode, card, session_state.cards)

        # For display progress: count tasks of this mode in the active queue
        active_queue = sm.get(sk.LEARNING_INCORRECT_CARDS, []) if reviewing else task_queue
        mode_tasks = [t for t in active_queue if t["mode"] == mode]
        mode_position = next((i for i, t in enumerate(active_queue) if t == task), 0)
        # Relative position within this mode-round
        mode_task_indices = [i for i, t in enumerate(active_queue) if t["mode"] == mode]
        rel_index = (
            mode_task_indices.index(mode_position) if mode_position in mode_task_indices else 0
        )

        return CardDisplayContext(
            card=card,
            index=rel_index,
            total=len(mode_tasks),
            task_index=task_index,
            task_total=len(active_queue),
            is_reviewing_incorrect=reviewing,
            active_tab=session_state.active_tab,
            sheet_gid=session_state.sheet_gid,
            mode=mode,
            mode_data=mode_data,
        )

    def _start_review_pass_or_finish(self, cards: list[dict]):
        """Switch to review pass or finish if no incorrect tasks."""
        incorrect_tasks = sm.get(sk.LEARNING_INCORRECT_CARDS, [])
        if incorrect_tasks:
            sm.set(sk.LEARNING_REVIEWING_INCORRECT, True)
            sm.set(sk.LEARNING_TASK_INDEX, 0)
            logger.info(f"Starting review pass: {len(incorrect_tasks)} tasks")
            return self.get_current_card_context()
        return None

    def _build_mode_data(self, mode: str, card: dict, all_cards: list[dict]) -> dict:
        """Generate mode-specific data for template rendering.

        Args:
            mode: LearningMode string
            card: Current card dict
            all_cards: All session card dicts (for distractor generation)

        Returns:
            Dict with mode-specific fields
        """
        if mode == LearningMode.PICK_ONE:
            card_obj = Card(**{k: v for k, v in card.items() if k in Card.model_fields})
            options = build_options(card_obj, all_cards)
            return {"options": options}

        if mode == LearningMode.BUILD_SENTENCE:
            sentence = card.get("example", "")
            return {"tiles": shuffle_words(sentence), "correct": sentence}

        if mode == LearningMode.BUILD_WORD:
            word = card.get("word", "")
            return {"tiles": shuffle_letters(word), "correct": word}

        # type_answer -- no extra data needed
        return {}

    # ------------------------------------------------------------------
    # Answer processing
    # ------------------------------------------------------------------

    def process_answer(self, user_answer: str) -> AnswerProcessResult:
        """Process the user's answer for the current task.

        Dispatches to mode-appropriate answer checking, updates card statistics,
        and tracks incorrect tasks for the review pass.

        Args:
            user_answer: The answer submitted by the user

        Returns:
            AnswerProcessResult with correctness and level change info
        """
        context = self.get_current_card_context()
        if not context:
            return AnswerProcessResult(success=False, error="No active session")

        card = context.card
        mode = context.mode
        reviewing = context.is_reviewing_incorrect

        is_correct = self._check_answer_for_mode(user_answer, card, mode)

        # Determine the card's actual index in session.cards
        task_queue = (
            sm.get(sk.LEARNING_TASK_QUEUE, [])
            if not reviewing
            else sm.get(sk.LEARNING_INCORRECT_CARDS, [])
        )
        task_index = sm.get(sk.LEARNING_TASK_INDEX, 0)
        task = task_queue[task_index]
        card_idx = task["card_idx"]

        # Update card statistics (level, counters)
        card_obj = Card(**{k: v for k, v in card.items() if k in Card.model_fields})
        result = self.stats.update_on_answer(card_obj, is_correct)
        updated_card = result.updated_card
        level_change = result.level_change

        self.session.update_card(card_idx, self.session._serialize_card(updated_card))

        # Record the answer
        answer_record = self._create_answer_record(
            card, user_answer, is_correct, reviewing, card_idx, mode
        )
        answers = sm.get(sk.LEARNING_ANSWERS, [])
        answers.append(answer_record)
        sm.set(sk.LEARNING_ANSWERS, answers)

        # Track failed tasks for review pass (first pass only)
        if not is_correct and not reviewing:
            incorrect = sm.get(sk.LEARNING_INCORRECT_CARDS, [])
            incorrect.append({"card_idx": card_idx, "mode": mode})
            sm.set(sk.LEARNING_INCORRECT_CARDS, incorrect)
            logger.info(f"Task queued for review: card {card_idx}, mode {mode}")

        sm.set(sk.LEARNING_LAST_LEVEL_CHANGE, level_change.to_dict())

        return AnswerProcessResult(
            success=True,
            is_correct=is_correct,
            level_change=level_change.to_dict(),
        )

    def _check_answer_for_mode(self, user_answer: str, card: dict, mode: str) -> bool:
        """Dispatch answer checking to the appropriate method for the mode."""
        if mode == LearningMode.PICK_ONE:
            return self.stats.check_answer_choice(user_answer, card.get("translation", ""))

        if mode == LearningMode.BUILD_SENTENCE:
            return self.stats.check_answer_ordered(user_answer, card.get("example", ""))

        if mode in (LearningMode.BUILD_WORD, LearningMode.TYPE_ANSWER):
            return self.stats.check_answer(user_answer, card.get("word", ""))

        # Fallback
        return self.stats.check_answer(user_answer, card.get("word", ""))

    @staticmethod
    def _create_answer_record(
        card: dict,
        user_answer: str,
        is_correct: bool,
        is_review: bool,
        card_index: int,
        mode: str,
    ) -> dict:
        """Create an answer record for session history."""
        from app.utils import get_timestamp

        correct_answer = card.get("word", "")
        if mode == LearningMode.PICK_ONE:
            correct_answer = card.get("translation", "")
        elif mode == LearningMode.BUILD_SENTENCE:
            correct_answer = card.get("example", "")

        return {
            "card_index": card_index,
            "word": card.get("word", ""),
            "translation": card.get("translation", ""),
            "user_answer": user_answer,
            "correct_answer": correct_answer,
            "is_correct": is_correct,
            "timestamp": get_timestamp().isoformat(),
            "is_review": is_review,
            "mode": mode,
        }

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def advance_to_next(self) -> None:
        """Advance to the next task in the queue."""
        task_index = sm.get(sk.LEARNING_TASK_INDEX, 0)
        sm.set(sk.LEARNING_TASK_INDEX, task_index + 1)

    def get_level_change(self) -> dict | None:
        """Get and clear the last level change info."""
        level_change = sm.get(sk.LEARNING_LAST_LEVEL_CHANGE)
        if level_change:
            sm.remove(sk.LEARNING_LAST_LEVEL_CHANGE)
        return level_change

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _batch_update_cards(self) -> bool:
        """Batch update modified cards to Google Sheets."""
        try:
            cards_data = sm.get(sk.LEARNING_CARDS, [])
            active_tab = sm.get(sk.LEARNING_ACTIVE_TAB)
            user = auth_manager.user
            user_spreadsheet_id = user.get_active_spreadsheet_id() if user else None

            if not cards_data or not active_tab or not user_spreadsheet_id:
                logger.warning("Missing session data for batch update")
                return False

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
            logger.info("Batch spreadsheet update completed")
            return True

        except Exception as e:
            logger.error(f"Error in batch update: {e}", exc_info=True)
            return False
