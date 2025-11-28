"""Card statistics and level progression logic.

This module handles card statistics updates and level progression,
extracted from route handlers to enable unit testing and reuse.
"""

import logging
from dataclasses import dataclass

from src.models import Card
from src.utils import get_timestamp

logger = logging.getLogger(__name__)


@dataclass
class LevelChange:
    """Represents a card level change after an answer."""

    from_level: int
    to_level: int
    is_correct: bool

    def to_dict(self) -> dict:
        """Convert to dictionary for session storage."""
        return {
            "from": self.from_level,
            "to": self.to_level,
            "is_correct": self.is_correct,
        }


@dataclass
class AnswerResult:
    """Result of processing an answer."""

    is_correct: bool
    level_change: LevelChange
    updated_card: Card


@dataclass
class SessionStats:
    """Statistics for a completed learning session."""

    total_answered: int
    correct_answers: int
    accuracy_percentage: int
    review_count: int
    first_attempt_count: int

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_answered": self.total_answered,
            "correct_answers": self.correct_answers,
            "accuracy_percentage": self.accuracy_percentage,
            "review_count": self.review_count,
            "first_attempt_count": self.first_attempt_count,
        }


class CardStatistics:
    """Handles card statistics updates and level progression."""

    @staticmethod
    def check_answer(user_answer: str, correct_answer: str) -> bool:
        """Check if user answer matches correct answer.

        Args:
            user_answer: Answer provided by user
            correct_answer: Expected correct answer

        Returns:
            True if answers match (case-insensitive, trimmed)
        """
        normalized_user = user_answer.strip().lower()
        normalized_correct = correct_answer.strip().lower()
        return normalized_user == normalized_correct

    @staticmethod
    def check_answer_multiple(user_answer: str, correct_answers: list[str]) -> bool:
        """Check if user answer matches any of the correct answers.

        Args:
            user_answer: Answer provided by user
            correct_answers: List of acceptable correct answers

        Returns:
            True if user answer matches any correct answer
        """
        normalized_user = user_answer.strip().lower()
        return any(normalized_user == correct.strip().lower() for correct in correct_answers)

    @staticmethod
    def update_on_answer(card: Card, is_correct: bool) -> AnswerResult:
        """Update card statistics based on answer.

        Updates:
        - cnt_shown (always incremented)
        - last_shown (set to current timestamp)
        - cnt_corr_answers (incremented if correct)
        - level (increased if correct, decreased if incorrect)

        Args:
            card: Card object to update
            is_correct: Whether the answer was correct

        Returns:
            AnswerResult with updated card and level change info
        """
        original_level = card.level.value

        # Update statistics
        card.cnt_shown += 1
        card.last_shown = get_timestamp()

        if is_correct:
            card.cnt_corr_answers += 1
            card.level = card.level.next_level()
            logger.info(f"✅ Correct! Level: {original_level} → {card.level.value}")
        else:
            card.level = card.level.previous_level()
            logger.info(f"❌ Incorrect! Level: {original_level} → {card.level.value}")

        level_change = LevelChange(
            from_level=original_level,
            to_level=card.level.value,
            is_correct=is_correct,
        )

        return AnswerResult(
            is_correct=is_correct,
            level_change=level_change,
            updated_card=card,
        )

    @staticmethod
    def calculate_session_stats(answers: list[dict]) -> SessionStats:
        """Calculate statistics for a learning session.

        Args:
            answers: List of answer records from session

        Returns:
            SessionStats with calculated statistics
        """
        total = len(answers)
        correct = sum(1 for a in answers if a.get("is_correct", False))
        review_answers = [a for a in answers if a.get("is_review", False)]

        accuracy = int((correct / total * 100) if total > 0 else 0)

        return SessionStats(
            total_answered=total,
            correct_answers=correct,
            accuracy_percentage=accuracy,
            review_count=len(review_answers),
            first_attempt_count=total - len(review_answers),
        )

    @staticmethod
    def create_answer_record(
        card: dict,
        user_answer: str,
        is_correct: bool,
        is_review: bool,
        card_index: int,
    ) -> dict:
        """Create an answer record for session history.

        Args:
            card: Card dict that was answered
            user_answer: User's submitted answer
            is_correct: Whether answer was correct
            is_review: Whether this was a review (second pass) attempt
            card_index: Index of the card in the session

        Returns:
            Answer record dict for session storage
        """
        return {
            "card_index": card_index,
            "word": card.get("word", ""),
            "translation": card.get("translation", ""),
            "user_answer": user_answer,
            "correct_answer": card.get("word", ""),
            "is_correct": is_correct,
            "timestamp": get_timestamp().isoformat(),
            "is_review": is_review,
        }
