"""Card session management for learning modes.

This module provides session state management for card-based learning,
abstracting the complexity of session key management and card serialization.
"""

import logging
from dataclasses import dataclass

from app.models import Card
from app.session_manager import SessionKeys as sk
from app.session_manager import SessionManager as sm
from app.utils import format_timestamp, parse_timestamp

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    """Represents current session state."""

    cards: list[dict]
    current_index: int
    active_tab: str
    sheet_gid: int
    is_valid: bool = True


class CardSessionManager:
    """Manages card session state for learning modes.

    Abstracts session key management and provides clean API for session operations.
    Supports both 'learn' (study) and 'review' modes with different session key namespaces.
    """

    def __init__(self, mode: str):
        """Initialize for specific mode.

        Args:
            mode: 'learn' for study sessions or 'review' for review sessions
        """
        self.mode = mode
        self._setup_keys()

    def _setup_keys(self) -> None:
        """Configure session keys based on mode."""
        if self.mode == "learn":
            self.cards_key = sk.LEARNING_CARDS
            self.index_key = sk.LEARNING_CURRENT_INDEX
            self.tab_key = sk.LEARNING_ACTIVE_TAB
            self.gid_key = sk.LEARNING_SHEET_GID
            self.namespace = "learning"
        else:  # review
            self.cards_key = sk.REVIEW_CARDS
            self.index_key = sk.REVIEW_CURRENT_INDEX
            self.tab_key = sk.REVIEW_ACTIVE_TAB
            self.gid_key = sk.REVIEW_SHEET_GID
            self.namespace = "review"

    def initialize(self, cards: list[Card], tab_name: str, gid: int) -> None:
        """Initialize session with cards.

        Args:
            cards: List of Card objects to store in session
            tab_name: Name of the active tab/worksheet
            gid: Google Sheet GID for the worksheet
        """
        cards_data = [self._serialize_card(card) for card in cards]
        sm.set(self.cards_key, cards_data)
        sm.set(self.index_key, 0)
        sm.set(self.tab_key, tab_name)
        sm.set(self.gid_key, gid)

        logger.info(f"Session initialized: {len(cards)} cards, tab={tab_name}, mode={self.mode}")

    def get_state(self) -> SessionState | None:
        """Get current session state.

        Returns:
            SessionState object if session is initialized, None otherwise
        """
        if not sm.has(self.cards_key) or not sm.has(self.index_key):
            return None

        return SessionState(
            cards=sm.get(self.cards_key),
            current_index=sm.get(self.index_key),
            active_tab=sm.get(self.tab_key, "Sheet1"),
            sheet_gid=sm.get(self.gid_key, 0),
        )

    def has_active_session(self) -> bool:
        """Check if there's an active session.

        Returns:
            True if session exists, False otherwise
        """
        return sm.has(self.cards_key) and sm.has(self.index_key)

    def get_current_card(self) -> dict | None:
        """Get the current card.

        Returns:
            Current card dict or None if session invalid or at end
        """
        state = self.get_state()
        if not state or state.current_index >= len(state.cards):
            return None
        return state.cards[state.current_index]

    def get_card_at_index(self, index: int) -> dict | None:
        """Get card at specific index.

        Args:
            index: Card index to retrieve

        Returns:
            Card dict at index or None if invalid
        """
        state = self.get_state()
        if not state or index < 0 or index >= len(state.cards):
            return None
        return state.cards[index]

    def get_current_index(self) -> int:
        """Get current card index.

        Returns:
            Current index or 0 if not set
        """
        return sm.get(self.index_key, 0)

    def get_total_cards(self) -> int:
        """Get total number of cards in session.

        Returns:
            Total card count or 0 if no session
        """
        cards = sm.get(self.cards_key, [])
        return len(cards)

    def set_index(self, index: int) -> None:
        """Set current card index.

        Args:
            index: New index value
        """
        sm.set(self.index_key, index)

    def advance(self) -> bool:
        """Move to next card.

        Returns:
            False if already at end, True otherwise
        """
        index = self.get_current_index()
        total = self.get_total_cards()

        if index >= total - 1:
            return False

        sm.set(self.index_key, index + 1)
        return True

    def update_card(self, card_index: int, card_data: dict) -> None:
        """Update a card in the session.

        Args:
            card_index: Index of card to update
            card_data: New card data dict
        """
        cards = sm.get(self.cards_key, [])
        if 0 <= card_index < len(cards):
            cards[card_index] = card_data
            sm.set(self.cards_key, cards)
            logger.debug(f"Updated card at index {card_index}")

    def get_all_cards(self) -> list[dict]:
        """Get all cards from session.

        Returns:
            List of card dicts or empty list if no session
        """
        return sm.get(self.cards_key, [])

    def clear(self) -> None:
        """Clear session data for this mode."""
        sm.clear_namespace(self.namespace)
        logger.info(f"Cleared {self.mode} session")

    @staticmethod
    def _serialize_card(card: Card) -> dict:
        """Serialize Card object for session storage.

        Args:
            card: Card object to serialize

        Returns:
            Dict representation suitable for JSON session storage
        """
        card_dict = card.model_dump()
        card_dict["last_shown"] = format_timestamp(card.last_shown)
        return card_dict

    @staticmethod
    def deserialize_card(card_data: dict) -> Card:
        """Deserialize card dict back to Card object.

        Args:
            card_data: Dict representation of card

        Returns:
            Card object
        """
        # Parse the timestamp back from string format
        if card_data.get("last_shown"):
            card_data = card_data.copy()  # Don't modify original
            card_data["last_shown"] = parse_timestamp(card_data["last_shown"])
        return Card(**card_data)
