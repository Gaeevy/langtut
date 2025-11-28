"""Tests for CardStatistics service."""

from src.models import Levels
from src.services.learning.statistics import AnswerResult, CardStatistics, SessionStats

from .conftest import make_card


class TestCheckAnswer:
    """Tests for CardStatistics.check_answer method."""

    def test_exact_match(self):
        """Exact match should return True."""
        assert CardStatistics.check_answer("hello", "hello") is True

    def test_case_insensitive(self):
        """Answer comparison should be case insensitive."""
        assert CardStatistics.check_answer("Hello", "hello") is True
        assert CardStatistics.check_answer("HELLO", "hello") is True

    def test_whitespace_trimmed(self):
        """Leading/trailing whitespace should be ignored."""
        assert CardStatistics.check_answer("  hello  ", "hello") is True
        assert CardStatistics.check_answer("hello", "  hello  ") is True

    def test_wrong_answer(self):
        """Wrong answer should return False."""
        assert CardStatistics.check_answer("goodbye", "hello") is False

    def test_empty_strings(self):
        """Empty strings should match each other."""
        assert CardStatistics.check_answer("", "") is True
        assert CardStatistics.check_answer("  ", "  ") is True


class TestCheckAnswerMultiple:
    """Tests for CardStatistics.check_answer_multiple method."""

    def test_matches_first_option(self):
        """Should match first correct answer."""
        assert CardStatistics.check_answer_multiple("hello", ["hello", "hi"]) is True

    def test_matches_second_option(self):
        """Should match second correct answer."""
        assert CardStatistics.check_answer_multiple("hi", ["hello", "hi"]) is True

    def test_no_match(self):
        """Should return False when no match."""
        assert CardStatistics.check_answer_multiple("goodbye", ["hello", "hi"]) is False

    def test_case_insensitive(self):
        """Should be case insensitive."""
        assert CardStatistics.check_answer_multiple("HELLO", ["hello", "hi"]) is True


class TestUpdateOnAnswer:
    """Tests for CardStatistics.update_on_answer method."""

    def test_correct_answer_increments_stats(self):
        """Correct answer should increment cnt_shown and cnt_corr_answers."""
        card = make_card(cnt_shown=0, cnt_corr_answers=0, level=Levels.LEVEL_0)

        result = CardStatistics.update_on_answer(card, is_correct=True)

        assert isinstance(result, AnswerResult)
        assert result.is_correct is True
        assert result.updated_card.cnt_shown == 1
        assert result.updated_card.cnt_corr_answers == 1

    def test_incorrect_answer_increments_shown_only(self):
        """Incorrect answer should only increment cnt_shown."""
        card = make_card(cnt_shown=0, cnt_corr_answers=0, level=Levels.LEVEL_3)

        result = CardStatistics.update_on_answer(card, is_correct=False)

        assert result.is_correct is False
        assert result.updated_card.cnt_shown == 1
        assert result.updated_card.cnt_corr_answers == 0

    def test_level_up_on_correct(self):
        """Correct answer should level up the card."""
        card = make_card(level=Levels.LEVEL_0)

        result = CardStatistics.update_on_answer(card, is_correct=True)

        assert result.updated_card.level == Levels.LEVEL_1
        assert result.level_change.from_level == 0
        assert result.level_change.to_level == 1
        assert result.level_change.is_correct is True

    def test_level_down_on_incorrect(self):
        """Incorrect answer should level down the card."""
        card = make_card(level=Levels.LEVEL_3)

        result = CardStatistics.update_on_answer(card, is_correct=False)

        assert result.updated_card.level == Levels.LEVEL_2
        assert result.level_change.from_level == 3
        assert result.level_change.to_level == 2
        assert result.level_change.is_correct is False

    def test_no_level_below_zero(self):
        """Level should not go below LEVEL_0."""
        card = make_card(level=Levels.LEVEL_0)

        result = CardStatistics.update_on_answer(card, is_correct=False)

        assert result.updated_card.level == Levels.LEVEL_0
        assert result.level_change.from_level == 0
        assert result.level_change.to_level == 0

    def test_no_level_above_max(self):
        """Level should not go above LEVEL_7."""
        card = make_card(level=Levels.LEVEL_7)

        result = CardStatistics.update_on_answer(card, is_correct=True)

        assert result.updated_card.level == Levels.LEVEL_7
        assert result.level_change.from_level == 7
        assert result.level_change.to_level == 7


class TestCalculateSessionStats:
    """Tests for CardStatistics.calculate_session_stats method."""

    def test_empty_session(self):
        """Empty session should return zero stats."""
        stats = CardStatistics.calculate_session_stats([])

        assert isinstance(stats, SessionStats)
        assert stats.total_answered == 0
        assert stats.correct_answers == 0
        assert stats.accuracy_percentage == 0

    def test_all_correct(self):
        """All correct answers should show 100% accuracy."""
        answers = [
            {"is_correct": True, "is_review": False},
            {"is_correct": True, "is_review": False},
            {"is_correct": True, "is_review": False},
        ]

        stats = CardStatistics.calculate_session_stats(answers)

        assert stats.total_answered == 3
        assert stats.correct_answers == 3
        assert stats.accuracy_percentage == 100
        assert stats.first_attempt_count == 3
        assert stats.review_count == 0

    def test_all_incorrect(self):
        """All incorrect answers should show 0% accuracy."""
        answers = [
            {"is_correct": False, "is_review": False},
            {"is_correct": False, "is_review": False},
        ]

        stats = CardStatistics.calculate_session_stats(answers)

        assert stats.total_answered == 2
        assert stats.correct_answers == 0
        assert stats.accuracy_percentage == 0

    def test_mixed_answers(self):
        """Mixed answers should calculate correct accuracy."""
        answers = [
            {"is_correct": True, "is_review": False},
            {"is_correct": False, "is_review": False},
            {"is_correct": True, "is_review": False},
            {"is_correct": True, "is_review": False},
        ]

        stats = CardStatistics.calculate_session_stats(answers)

        assert stats.total_answered == 4
        assert stats.correct_answers == 3
        assert stats.accuracy_percentage == 75

    def test_review_count(self):
        """Should correctly count review attempts."""
        answers = [
            {"is_correct": True, "is_review": False},
            {"is_correct": False, "is_review": False},
            {"is_correct": True, "is_review": True},  # Review attempt
        ]

        stats = CardStatistics.calculate_session_stats(answers)

        assert stats.total_answered == 3
        assert stats.review_count == 1
        assert stats.first_attempt_count == 2
