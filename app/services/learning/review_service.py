"""Review mode service - orchestrates review session logic."""

import logging
from dataclasses import dataclass
from enum import StrEnum

from app.gsheet import read_card_set, update_spreadsheet
from app.services.learning.card_session import CardSessionManager
from app.utils import get_timestamp

logger = logging.getLogger(__name__)


class ReviewOutcome(StrEnum):
    """Available self-assessment choices for a reviewed card."""

    FORGOTTEN = "forgotten"
    REMEMBERED = "remembered"


@dataclass
class ReviewSessionResult:
    """Result of initializing a review session."""

    success: bool
    card_count: int = 0
    error: str | None = None


@dataclass
class ReviewCardContext:
    """Context for displaying a review card."""

    card: dict
    index: int
    total: int
    active_tab: str
    sheet_gid: int
    mode: str = "review"


@dataclass
class ReviewActionResult:
    """Result of recording a review choice and advancing the stack."""

    success: bool
    completed: bool = False
    error: str | None = None


class ReviewService:
    """Service for reviewing every card in a set once."""

    def __init__(self):
        """Initialize the review service."""
        self.session = CardSessionManager("review")

    def start_session(self, tab_name: str, spreadsheet_id: str) -> ReviewSessionResult:
        """Start a new review session with ALL cards.

        Args:
            tab_name: Name of the worksheet/tab to review
            spreadsheet_id: Google Sheets spreadsheet ID

        Returns:
            ReviewSessionResult with success status and card count
        """
        try:
            # Read card set from Google Sheets
            card_set = read_card_set(worksheet_name=tab_name, spreadsheet_id=spreadsheet_id)

            if not card_set:
                return ReviewSessionResult(success=False, error=f"Card set '{tab_name}' not found")

            # Get ALL cards (no filtering for review mode), oldest reviewed first.
            # Python's sort is stable, so cards with the same timestamp retain
            # their worksheet order.
            cards = sorted(card_set.cards, key=lambda card: card.last_shown)

            if not cards:
                return ReviewSessionResult(success=False, error="No cards in this set")

            # Initialize session with cards
            self.session.initialize(cards, tab_name, card_set.gid)

            logger.info(f"Review session started: {len(cards)} cards from '{tab_name}'")

            return ReviewSessionResult(success=True, card_count=len(cards))

        except Exception as e:
            logger.error(f"Error starting review session: {e}", exc_info=True)
            return ReviewSessionResult(success=False, error=str(e))

    def get_current_card_context(self) -> ReviewCardContext | None:
        """Get context for displaying the current card.

        Returns:
            ReviewCardContext for template rendering, or None if no session
        """
        state = self.session.get_state()
        if not state:
            return None

        # Safety check for index bounds
        index = state.current_index
        if index >= len(state.cards):
            logger.warning(f"Review index {index} out of bounds, resetting to 0")
            self.session.set_index(0)
            index = 0

        card = state.cards[index].copy()
        card["is_review"] = False  # This flag is for learn mode's incorrect card review

        return ReviewCardContext(
            card=card,
            index=index,
            total=len(state.cards),
            active_tab=state.active_tab,
            sheet_gid=state.sheet_gid,
        )

    def navigate(self, direction: str) -> bool:
        """Navigate between cards with wraparound.

        Args:
            direction: 'next' or 'prev'

        Returns:
            True if navigation successful, False if no session
        """
        state = self.session.get_state()
        if not state:
            return False

        total = len(state.cards)
        current = state.current_index

        if direction == "next":
            new_index = (current + 1) % total  # Wraparound to 0 after last
        elif direction == "prev":
            new_index = (current - 1) % total  # Wraparound to last before first
        else:
            logger.error(f"Invalid navigation direction: {direction}")
            return False

        self.session.set_index(new_index)
        logger.debug(f"Review navigation: {current} -> {new_index} ({direction})")
        return True

    def record_review(self, outcome: ReviewOutcome, spreadsheet_id: str) -> ReviewActionResult:
        """Record one review choice and advance to the next card.

        Remembered cards retain their level. Forgotten cards lose one level.
        Both choices update ``last_shown`` in the session. The complete stack
        is written to Google Sheets once, after the final card is reviewed.
        """
        state = self.session.get_state()
        if not state or state.current_index >= len(state.cards):
            return ReviewActionResult(success=False, error="No active review card")

        card = self.session.deserialize_card(state.cards[state.current_index])
        original_level = card.level.value
        card.last_shown = get_timestamp()
        if outcome == ReviewOutcome.FORGOTTEN:
            card.level = card.level.previous_level()

        updated_card = self.session.serialize_card(card)
        logger.info(
            "Recorded review for card %s: outcome=%s, level=%s→%s",
            card.id,
            outcome,
            original_level,
            card.level.value,
        )

        if state.current_index == len(state.cards) - 1:
            cards_to_save = [
                updated_card if index == state.current_index else card_data
                for index, card_data in enumerate(state.cards)
            ]
            try:
                self._save_cards(state.active_tab, cards_to_save, spreadsheet_id)
            except Exception as error:
                logger.error("Failed to save review session: %s", error, exc_info=True)
                return ReviewActionResult(success=False, error="Could not save review progress")

            self._clear_session()
            return ReviewActionResult(success=True, completed=True)

        self.session.update_card(state.current_index, updated_card)
        self.session.set_index(state.current_index + 1)
        return ReviewActionResult(success=True)

    def has_active_session(self) -> bool:
        """Check if there's an active review session.

        Returns:
            True if session exists
        """
        return self.session.has_active_session()

    def end_session_early(self, spreadsheet_id: str) -> ReviewActionResult:
        """Save reviewed cards and end an incomplete review session."""
        state = self.session.get_state()
        if not state:
            return ReviewActionResult(success=False, error="No active review session")

        reviewed_cards = state.cards[: state.current_index]
        try:
            self._save_cards(state.active_tab, reviewed_cards, spreadsheet_id)
        except Exception as error:
            logger.error("Failed to save partial review session: %s", error, exc_info=True)
            return ReviewActionResult(success=False, error="Could not save review progress")

        logger.info(
            "Saved %s reviewed cards before ending session early",
            len(reviewed_cards),
        )
        self._clear_session()
        return ReviewActionResult(success=True, completed=True)

    def _save_cards(
        self,
        active_tab: str,
        cards_data: list[dict],
        spreadsheet_id: str,
    ) -> None:
        """Deserialize and batch-save review-session cards."""
        if not cards_data:
            return
        cards = [self.session.deserialize_card(card_data) for card_data in cards_data]
        update_spreadsheet(active_tab, cards, spreadsheet_id=spreadsheet_id)

    def _clear_session(self) -> None:
        """Clear review session data after a successful completion or early end."""
        self.session.clear()
        logger.info("Review session ended")
