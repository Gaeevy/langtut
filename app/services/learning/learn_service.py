"""Learn mode service - orchestrates learn session logic.

The session is built as a task queue: an ordered list of {card_idx, mode} pairs.
Cards appear multiple times in the queue (once per mode in their pipeline).
A single task index walks the full queue.

Key behaviours:
- Wrong answer: the task is appended to the END of the queue (retry until correct).
- Level and cnt_corr_answers: applied once at end_session via _finalize_pipeline_outcomes
  for cards whose full pipeline was completed in session (same up/down rule as before).
- No separate review pass -- retried tasks are simply part of the main queue.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field

from app.config import config
from app.gsheet import read_card_set, update_spreadsheet
from app.models import Card
from app.services.auth_manager import auth_manager
from app.session_manager import SessionKeys as sk
from app.session_manager import SessionManager as sm
from app.utils import get_timestamp, parse_timestamp

from .card_session import CardSessionManager
from .mode_config import (
    GLOBAL_MODE_ORDER,
    MODE_SECTION_LABELS,
    LearningMode,
    build_options,
    build_task_queue,
    build_translation_options,
    compute_queue_section_defs,
    get_pipeline,
    shuffle_words,
    sort_letters,
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
    task_index: int  # current position in the queue (0-based)
    task_total: int  # current queue length (grows when retries are added)
    active_tab: str
    sheet_gid: int
    mode: str = LearningMode.TYPE_ANSWER
    mode_data: dict = field(default_factory=dict)
    progress_sections: list[dict] = field(default_factory=list)
    initial_task_length: int = 0


@dataclass
class AnswerProcessResult:
    """Result of processing an answer."""

    success: bool
    is_correct: bool = False
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
    per_card_breakdown: list[dict] = field(default_factory=list)
    session_tab: str | None = None


def _merge_progress_sections_with_review(
    base_defs: list[dict],
    current_queue_len: int,
    initial_len: int,
) -> list[dict]:
    """Append a Review segment when retries extended the queue past the initial length."""
    out = [{**s} for s in base_defs]
    if current_queue_len > initial_len:
        out.append(
            {
                "mode": "review",
                "label": "Review",
                "start": initial_len,
                "length": current_queue_len - initial_len,
            }
        )
    return out


def _enrich_progress_sections(task_index: int, sections: list[dict]) -> list[dict]:
    """Add fill_pct, fill_fraction, and is_current for template / JSON consumers."""
    enriched: list[dict] = []
    for s in sections:
        start = int(s["start"])
        length = max(int(s["length"]), 1)
        raw = (task_index - start) / length
        fill = max(0.0, min(1.0, raw))
        fill_pct = round(fill * 100)
        is_current = start <= task_index < start + length
        enriched.append(
            {
                **s,
                "fill_pct": fill_pct,
                "fill_fraction": fill,
                "is_current": is_current,
            }
        )
    return enriched


class LearnService:
    """Service for learn mode operations."""

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

            self.session.initialize(cards, tab_name, card_set.gid)

            task_queue = build_task_queue(cards)
            initial_len = len(task_queue)
            section_defs = compute_queue_section_defs(task_queue)
            sm.set(sk.LEARNING_TASK_QUEUE, task_queue)
            sm.set(sk.LEARNING_TASK_INDEX, 0)
            sm.set(sk.LEARNING_TASK_INITIAL_LENGTH, initial_len)
            sm.set(sk.LEARNING_TASK_SECTION_DEFS, section_defs)
            sm.set(
                sk.LEARNING_CARD_START_LEVELS,
                {str(i): card.level.value for i, card in enumerate(cards)},
            )

            # Store original pipeline per card (used for completion check)
            card_pipelines = {
                str(i): list(get_pipeline(card.level)) for i, card in enumerate(cards)
            }
            sm.set(sk.LEARNING_CARD_PIPELINES, card_pipelines)
            sm.set(sk.LEARNING_CARD_MODES_DONE, {})
            sm.set(sk.LEARNING_CARD_RETRIES, {})

            sm.set(sk.LEARNING_ANSWERS, [])
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
        """End the learn session and return results."""
        answers = sm.get(sk.LEARNING_ANSWERS, [])
        original_count = sm.get(sk.LEARNING_ORIGINAL_COUNT, len(answers))
        session_tab = sm.get(sk.LEARNING_ACTIVE_TAB)

        self._finalize_pipeline_outcomes()

        per_card_breakdown = self._build_per_card_breakdown(answers)

        stats = self.stats.calculate_session_stats(answers)

        update_successful = self._batch_update_cards()

        cards_remaining = 0
        if early:
            task_queue = sm.get(sk.LEARNING_TASK_QUEUE, [])
            task_index = sm.get(sk.LEARNING_TASK_INDEX, 0)
            cards_remaining = max(0, len(task_queue) - task_index)

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
            per_card_breakdown=per_card_breakdown,
            session_tab=session_tab,
        )

    # ------------------------------------------------------------------
    # Card display
    # ------------------------------------------------------------------

    def get_current_card_context(self) -> CardDisplayContext | None:
        """Get context for displaying the current task (card + mode).

        Returns None when the queue is exhausted (session complete).
        """
        session_state = self.session.get_state()
        if not session_state:
            return None

        task_queue = sm.get(sk.LEARNING_TASK_QUEUE, [])
        task_index = sm.get(sk.LEARNING_TASK_INDEX, 0)

        if task_index >= len(task_queue):
            return None  # Queue exhausted, session complete

        task = task_queue[task_index]
        card_idx = task["card_idx"]
        mode = task["mode"]

        card = session_state.cards[card_idx].copy()
        card["is_review"] = False

        mode_data = self._build_mode_data(mode, card, session_state.cards)

        initial_len = sm.get(sk.LEARNING_TASK_INITIAL_LENGTH, len(task_queue))
        base_defs = sm.get(sk.LEARNING_TASK_SECTION_DEFS, [])
        merged = _merge_progress_sections_with_review(base_defs, len(task_queue), initial_len)
        progress_sections = _enrich_progress_sections(task_index, merged)

        return CardDisplayContext(
            card=card,
            task_index=task_index,
            task_total=len(task_queue),
            active_tab=session_state.active_tab,
            sheet_gid=session_state.sheet_gid,
            mode=mode,
            mode_data=mode_data,
            progress_sections=progress_sections,
            initial_task_length=initial_len,
        )

    def _build_mode_data(self, mode: str, card: dict, all_cards: list[dict]) -> dict:
        """Generate mode-specific data for template rendering."""
        if mode == LearningMode.PICK_ONE:
            card_obj = Card(**{k: v for k, v in card.items() if k in Card.model_fields})
            options = build_options(card_obj, all_cards)
            return {"options": options}

        if mode == LearningMode.PICK_TRANSLATION:
            card_obj = Card(**{k: v for k, v in card.items() if k in Card.model_fields})
            options = build_translation_options(card_obj, all_cards)
            return {"options": options}

        if mode == LearningMode.BUILD_SENTENCE:
            sentence = card.get("example", "")
            return {"tiles": shuffle_words(sentence), "correct": sentence}

        if mode == LearningMode.BUILD_WORD:
            word = card.get("word", "")
            return {"tiles": sort_letters(word), "correct": word}

        return {}

    # ------------------------------------------------------------------
    # Answer processing
    # ------------------------------------------------------------------

    def process_answer(self, user_answer: str) -> AnswerProcessResult:
        """Process the user's answer for the current task.

        Correct answer: marks the mode as done for the card. Level and
        cnt_corr_answers are applied once at end_session when the full pipeline
        for that card is complete.

        Wrong answer: increments the card's retry count and appends the task to
        the end of the queue so the user tries again later.
        """
        session_state = self.session.get_state()
        if not session_state:
            return AnswerProcessResult(success=False, error="No active session")

        task_queue = sm.get(sk.LEARNING_TASK_QUEUE, [])
        task_index = sm.get(sk.LEARNING_TASK_INDEX, 0)

        if task_index >= len(task_queue):
            return AnswerProcessResult(success=False, error="No active task")

        task = task_queue[task_index]
        card_idx = task["card_idx"]
        mode = task["mode"]
        card = session_state.cards[card_idx].copy()
        card_key = str(card_idx)

        is_correct = self._check_answer_for_mode(user_answer, card, mode)

        card_retries = sm.get(sk.LEARNING_CARD_RETRIES, {})
        card_modes_done = sm.get(sk.LEARNING_CARD_MODES_DONE, {})

        # Deserialize card for stat updates
        card_obj = self.session.deserialize_card(card)

        # Update cnt_shown and last_shown the first time this card appears
        is_first_encounter = card_key not in card_modes_done and card_retries.get(card_key, 0) == 0
        if is_first_encounter:
            card_obj.cnt_shown += 1
            card_obj.last_shown = get_timestamp()

        if is_correct:
            # Mark this mode as completed for this card (level/cnt_corr at end_session).
            if card_key not in card_modes_done:
                card_modes_done[card_key] = []
            if mode not in card_modes_done[card_key]:
                card_modes_done[card_key].append(mode)
            sm.set(sk.LEARNING_CARD_MODES_DONE, card_modes_done)

        else:
            # Wrong: track retry and re-queue the task
            card_retries[card_key] = card_retries.get(card_key, 0) + 1
            sm.set(sk.LEARNING_CARD_RETRIES, card_retries)

            task_queue.append({"card_idx": card_idx, "mode": mode})
            sm.set(sk.LEARNING_TASK_QUEUE, task_queue)

            logger.info(
                f"Wrong answer for card {card_idx} ({mode}), re-queued. "
                f"Retry #{card_retries[card_key]}"
            )

        # Persist updated card
        self.session.update_card(card_idx, self.session._serialize_card(card_obj))

        # Record answer
        answer_record = self._create_answer_record(card, user_answer, is_correct, card_idx, mode)
        answers = sm.get(sk.LEARNING_ANSWERS, [])
        answers.append(answer_record)
        sm.set(sk.LEARNING_ANSWERS, answers)

        return AnswerProcessResult(
            success=True,
            is_correct=is_correct,
        )

    def _check_answer_for_mode(self, user_answer: str, card: dict, mode: str) -> bool:
        """Dispatch answer checking to the appropriate method for the mode."""
        if mode == LearningMode.PICK_ONE:
            return self.stats.check_answer_choice(user_answer, card.get("word", ""))

        if mode == LearningMode.PICK_TRANSLATION:
            return self.stats.check_answer_choice(user_answer, card.get("translation", ""))

        if mode == LearningMode.BUILD_SENTENCE:
            return self.stats.check_answer_ordered(user_answer, card.get("example", ""))

        if mode == LearningMode.WRITE_EXAMPLE:
            return self.stats.check_answer_ordered(user_answer, card.get("example", ""))

        # build_word and type_answer both check against the target word
        return self.stats.check_answer(user_answer, card.get("word", ""))

    @staticmethod
    def _create_answer_record(
        card: dict,
        user_answer: str,
        is_correct: bool,
        card_index: int,
        mode: str,
    ) -> dict:
        """Create an answer record for session history."""
        correct_answer = card.get("word", "")
        if mode == LearningMode.PICK_TRANSLATION:
            correct_answer = card.get("translation", "")
        elif mode in (LearningMode.BUILD_SENTENCE, LearningMode.WRITE_EXAMPLE):
            correct_answer = card.get("example", "")

        return {
            "card_index": card_index,
            "word": card.get("word", ""),
            "translation": card.get("translation", ""),
            "user_answer": user_answer,
            "correct_answer": correct_answer,
            "is_correct": is_correct,
            "timestamp": get_timestamp().isoformat(),
            "is_review": False,
            "mode": mode,
        }

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def advance_to_next(self) -> None:
        """Advance to the next task in the queue."""
        task_index = sm.get(sk.LEARNING_TASK_INDEX, 0)
        sm.set(sk.LEARNING_TASK_INDEX, task_index + 1)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _finalize_pipeline_outcomes(self) -> None:
        """Increment cnt_corr_answers and adjust level for cards that completed their pipeline."""
        session_state = self.session.get_state()
        if not session_state:
            return

        cards_data = session_state.cards
        card_pipelines = sm.get(sk.LEARNING_CARD_PIPELINES, {})
        card_modes_done = sm.get(sk.LEARNING_CARD_MODES_DONE, {})
        card_retries = sm.get(sk.LEARNING_CARD_RETRIES, {})

        for idx in range(len(cards_data)):
            card_key = str(idx)
            pipeline = card_pipelines.get(card_key)
            if not pipeline:
                continue

            pipeline_modes = [str(m) for m in pipeline]
            done_list = card_modes_done.get(card_key, [])
            done_set = {str(m) for m in done_list}

            if not all(m in done_set for m in pipeline_modes):
                continue

            retries = card_retries.get(card_key, 0)
            max_allowed_retries = max(0, len(pipeline_modes) - 1)

            card_obj = self.session.deserialize_card(cards_data[idx])
            original_level = card_obj.level.value

            card_obj.cnt_corr_answers += 1
            if retries <= max_allowed_retries:
                card_obj.level = card_obj.level.next_level()
            else:
                card_obj.level = card_obj.level.previous_level()

            self.session.update_card(idx, self.session._serialize_card(card_obj))
            logger.info(
                f"Finalized card {idx}: retries={retries}, max={max_allowed_retries}, "
                f"level {original_level}→{card_obj.level.value}"
            )

    def _build_per_card_breakdown(self, answers: list[dict]) -> list[dict]:
        """Build per-word stats for the session results screen."""
        cards_data = sm.get(sk.LEARNING_CARDS, [])
        start_levels = sm.get(sk.LEARNING_CARD_START_LEVELS, {})

        by_index: dict[int, list[dict]] = defaultdict(list)
        for a in answers:
            by_index[int(a["card_index"])].append(a)

        result: list[dict] = []
        for idx in sorted(by_index.keys()):
            rows = sorted(by_index[idx], key=lambda x: x.get("timestamp", ""))
            word = str(rows[0].get("word", ""))
            translation = str(rows[0].get("translation", ""))
            by_mode: dict[str, dict[str, int | bool]] = {}
            for rec in rows:
                m = str(rec["mode"])
                if m not in by_mode:
                    by_mode[m] = {
                        "attempts": 0,
                        "correct_count": 0,
                        "final_ok": False,
                        "first_ok": bool(rec.get("is_correct")),
                    }
                by_mode[m]["attempts"] += 1
                if rec.get("is_correct"):
                    by_mode[m]["correct_count"] += 1
                by_mode[m]["final_ok"] = bool(rec.get("is_correct"))

            mode_order = [m.value for m in GLOBAL_MODE_ORDER]
            mode_entries: list[dict[str, str | int | bool]] = []
            for m in mode_order:
                if m not in by_mode:
                    continue
                st = by_mode[m]
                mode_entries.append(
                    {
                        "mode": m,
                        "label": MODE_SECTION_LABELS.get(m, m),
                        "attempts": int(st["attempts"]),
                        "correct_count": int(st["correct_count"]),
                        "final_ok": bool(st["final_ok"]),
                        "first_ok": bool(st["first_ok"]),
                    }
                )
            for m, st in by_mode.items():
                if m in mode_order:
                    continue
                mode_entries.append(
                    {
                        "mode": m,
                        "label": MODE_SECTION_LABELS.get(m, m),
                        "attempts": int(st["attempts"]),
                        "correct_count": int(st["correct_count"]),
                        "final_ok": bool(st["final_ok"]),
                        "first_ok": bool(st["first_ok"]),
                    }
                )

            end_level = 0
            if idx < len(cards_data):
                raw = cards_data[idx]
                try:
                    end_level = self.session.deserialize_card(raw).level.value
                except Exception:
                    lv = raw.get("level", 0)
                    end_level = lv.value if hasattr(lv, "value") else int(lv)

            start_level = int(start_levels.get(str(idx), end_level))

            result.append(
                {
                    "card_index": idx,
                    "word": word,
                    "translation": translation,
                    "start_level": start_level,
                    "end_level": end_level,
                    "by_mode": by_mode,
                    "mode_entries": mode_entries,
                }
            )
        return result

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
