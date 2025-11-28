"""Review mode service - orchestrates review session logic.

This service handles browse/review sessions where users can flip through
all cards without answering - simpler than learn mode.
"""

import logging
from dataclasses import dataclass

from app.gsheet import read_card_set

from .card_session import CardSessionManager

logger = logging.getLogger(__name__)


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


class ReviewService:
    """Service for review mode operations (browse all cards).

    Review mode allows users to flip through all cards in a set
    without answering - useful for quick review or memorization.

    Features:
    - No answer validation
    - Wraparound navigation (prev/next)
    - Card flip to see answer
    - No statistics updates
    """

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

            # Get ALL cards (no filtering for review mode)
            cards = card_set.cards

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

    def has_active_session(self) -> bool:
        """Check if there's an active review session.

        Returns:
            True if session exists
        """
        return self.session.has_active_session()

    def end_session(self) -> None:
        """End the review session and clear data."""
        self.session.clear()
        logger.info("Review session ended")
