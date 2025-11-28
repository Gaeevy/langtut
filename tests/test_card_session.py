"""Tests for CardSessionManager service."""

from app.models import Levels
from app.services.learning.card_session import CardSessionManager

from .conftest import make_card


class TestCardSessionManagerInit:
    """Tests for CardSessionManager initialization."""

    def test_learn_mode_uses_learning_keys(self, request_context):
        """Learn mode should use LEARNING_* session keys."""
        manager = CardSessionManager("learn")

        assert manager.mode == "learn"
        assert "LEARNING" in str(manager.cards_key)

    def test_review_mode_uses_review_keys(self, request_context):
        """Review mode should use REVIEW_* session keys."""
        manager = CardSessionManager("review")

        assert manager.mode == "review"
        assert "REVIEW" in str(manager.cards_key)


class TestCardSessionManagerOperations:
    """Tests for CardSessionManager session operations."""

    def test_initialize_stores_cards(self, request_context):
        """Initialize should store cards in session."""
        manager = CardSessionManager("learn")
        cards = [
            make_card(id=1, word="olá", translation="hello"),
            make_card(id=2, word="obrigado", translation="thank you"),
        ]

        manager.initialize(cards, "Test Tab", 12345)

        state = manager.get_state()
        assert state is not None
        assert len(state.cards) == 2
        assert state.active_tab == "Test Tab"
        assert state.sheet_gid == 12345
        assert state.current_index == 0

    def test_has_active_session_false_when_empty(self, request_context):
        """has_active_session should return False when no session."""
        manager = CardSessionManager("learn")

        assert manager.has_active_session() is False

    def test_has_active_session_true_after_initialize(self, request_context):
        """has_active_session should return True after initialization."""
        manager = CardSessionManager("learn")
        cards = [make_card(id=1)]

        manager.initialize(cards, "Test Tab", 12345)

        assert manager.has_active_session() is True

    def test_get_state_returns_none_when_empty(self, request_context):
        """get_state should return None when no session."""
        manager = CardSessionManager("learn")

        assert manager.get_state() is None

    def test_set_index_updates_current_index(self, request_context):
        """set_index should update the current index."""
        manager = CardSessionManager("learn")
        cards = [
            make_card(id=1, word="olá"),
            make_card(id=2, word="obrigado"),
        ]
        manager.initialize(cards, "Test Tab", 12345)

        manager.set_index(1)

        state = manager.get_state()
        assert state.current_index == 1

    def test_clear_removes_session_data(self, request_context):
        """clear should remove all session data."""
        manager = CardSessionManager("learn")
        cards = [make_card(id=1)]
        manager.initialize(cards, "Test Tab", 12345)

        manager.clear()

        assert manager.has_active_session() is False
        assert manager.get_state() is None


class TestCardSessionManagerCardOperations:
    """Tests for CardSessionManager card-level operations."""

    def test_get_current_card(self, request_context):
        """get_current_card should return the current card."""
        manager = CardSessionManager("learn")
        cards = [
            make_card(id=1, word="olá"),
            make_card(id=2, word="obrigado"),
        ]
        manager.initialize(cards, "Test Tab", 12345)

        card = manager.get_current_card()

        assert card is not None
        assert card["word"] == "olá"

    def test_get_current_card_after_index_change(self, request_context):
        """get_current_card should return card at current index."""
        manager = CardSessionManager("learn")
        cards = [
            make_card(id=1, word="olá"),
            make_card(id=2, word="obrigado"),
        ]
        manager.initialize(cards, "Test Tab", 12345)
        manager.set_index(1)

        card = manager.get_current_card()

        assert card is not None
        assert card["word"] == "obrigado"

    def test_update_card_modifies_stored_card(self, request_context):
        """update_card should modify the card in session."""
        manager = CardSessionManager("learn")
        cards = [make_card(id=1, word="olá", level=Levels.LEVEL_0)]
        manager.initialize(cards, "Test Tab", 12345)

        # Create updated card with higher level (convert to dict for update)
        updated_card = make_card(id=1, word="olá", level=Levels.LEVEL_1, cnt_corr_answers=1)
        manager.update_card(0, updated_card.model_dump())

        # Retrieve and verify
        card = manager.get_current_card()
        assert card["level"] == Levels.LEVEL_1.value
        assert card["cnt_corr_answers"] == 1

    def test_get_all_cards(self, request_context):
        """get_all_cards should return all cards in session."""
        manager = CardSessionManager("learn")
        cards = [
            make_card(id=1, word="olá"),
            make_card(id=2, word="obrigado"),
        ]
        manager.initialize(cards, "Test Tab", 12345)

        all_cards = manager.get_all_cards()

        assert len(all_cards) == 2
