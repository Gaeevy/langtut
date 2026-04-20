"""Tests for LearnService pipeline and level progression."""

from unittest.mock import patch

from app.models import Levels
from app.services.learning.card_session import CardSessionManager
from app.services.learning.learn_service import LearnService
from app.services.learning.mode_config import LearningMode
from app.session_manager import SessionKeys as sk
from app.session_manager import SessionManager as sm
from tests.conftest import make_card


class TestLearnServiceLevelBumpAtPipelineEnd:
    """Card level and cnt_corr update only in end_session after full pipeline completion."""

    def test_level_unchanged_until_end_session_finalize(self, request_context):
        """Mid-pipeline answers do not change level; finalize at end_session bumps level."""
        card = make_card(id=1, level=Levels.LEVEL_0)
        manager = CardSessionManager("learn")
        manager.initialize([card], "TestTab", 1)

        # One card at level 0: pipeline is pick_one, build_sentence, pick_translation
        task_queue = [
            {"card_idx": 0, "mode": LearningMode.PICK_TRANSLATION},
            {"card_idx": 0, "mode": LearningMode.PICK_ONE},
            {"card_idx": 0, "mode": LearningMode.BUILD_SENTENCE},
        ]
        sm.set(sk.LEARNING_TASK_QUEUE, task_queue)
        sm.set(sk.LEARNING_TASK_INDEX, 0)
        sm.set(
            sk.LEARNING_CARD_PIPELINES,
            {
                "0": [
                    LearningMode.PICK_ONE,
                    LearningMode.BUILD_SENTENCE,
                    LearningMode.PICK_TRANSLATION,
                ]
            },
        )
        sm.set(sk.LEARNING_CARD_START_LEVELS, {"0": 0})
        sm.set(sk.LEARNING_ORIGINAL_COUNT, 1)
        sm.set(sk.LEARNING_CARD_MODES_DONE, {})
        sm.set(sk.LEARNING_CARD_RETRIES, {})
        sm.set(sk.LEARNING_ANSWERS, [])

        service = LearnService()

        r0_wrong = service.process_answer("wrong translation attempt")
        assert r0_wrong.success and not r0_wrong.is_correct
        assert _card_level(service, 0) == Levels.LEVEL_0

        r0 = service.process_answer(card.translation)
        assert r0.success and r0.is_correct
        assert _card_level(service, 0) == Levels.LEVEL_0

        service.advance_to_next()

        r1 = service.process_answer(card.word)
        assert r1.success and r1.is_correct
        assert _card_level(service, 0) == Levels.LEVEL_0

        service.advance_to_next()

        r2 = service.process_answer(card.example)
        assert r2.success and r2.is_correct
        assert _card_level(service, 0) == Levels.LEVEL_0

        with patch.object(LearnService, "_batch_update_cards", return_value=True):
            end = service.end_session(early=False)

        assert end.per_card_breakdown
        row = end.per_card_breakdown[0]
        assert row["start_level"] == 0
        assert row["end_level"] == 1
        by_mode = {e["mode"]: e for e in row["mode_entries"]}
        assert by_mode["pick_translation"]["first_ok"] is False
        assert by_mode["pick_translation"]["final_ok"] is True


def _card_level(service: LearnService, card_idx: int) -> Levels:
    """Read card level from session after deserialize."""
    state = service.session.get_state()
    assert state is not None
    raw = state.cards[card_idx]
    return service.session.deserialize_card(raw).level
