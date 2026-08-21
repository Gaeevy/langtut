"""Tests for LearnService pipeline and level progression."""

from unittest.mock import patch

import pytest

from app.models import Levels
from app.services.learning.card_session import CardSessionManager
from app.services.learning.learn_service import LearnService
from app.services.learning.mode_config import LearningMode
from app.session_manager import SessionKeys as sk
from app.session_manager import SessionManager as sm
from tests.conftest import make_card


class TestUniformAnswerComparison:
    """Every learning mode uses the same processed-token comparison."""

    @pytest.mark.parametrize(
        ("mode", "user_answer"),
        [
            (LearningMode.PICK_ONE, '"OLÁ"'),
            (LearningMode.PICK_TRANSLATION, "HELLO!!!"),
            (LearningMode.BUILD_SENTENCE, "qwe asd"),
            (LearningMode.BUILD_WORD, "OLÁ"),
            (LearningMode.TYPE_ANSWER, "olá..."),
            (LearningMode.TYPE_EXAMPLE_GUIDED, "QWE / ASD"),
            (LearningMode.WRITE_EXAMPLE, "qwe; asd?"),
        ],
    )
    def test_mode_ignores_symbols_and_case(self, mode, user_answer, request_context):
        card = make_card(word="Olá!", translation="Hello.", example="qwe \\\\\\ asd")

        assert LearnService()._check_answer_for_mode(user_answer, card.model_dump(), mode) is True


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


class TestTypeExampleGuidedMode:
    """type_example_guided checks full example sentence; answer record uses example."""

    def test_process_answer_guided_mode(self, request_context):
        card = make_card(
            id=1,
            level=Levels.LEVEL_6,
            example="não me parece",
            example_translation="it does not seem to me",
        )
        manager = CardSessionManager("learn")
        manager.initialize([card], "TestTab", 1)

        sm.set(sk.LEARNING_TASK_QUEUE, [{"card_idx": 0, "mode": LearningMode.TYPE_EXAMPLE_GUIDED}])
        sm.set(sk.LEARNING_TASK_INDEX, 0)
        sm.set(sk.LEARNING_CARD_PIPELINES, {"0": [LearningMode.TYPE_EXAMPLE_GUIDED]})
        sm.set(sk.LEARNING_CARD_START_LEVELS, {"0": 6})
        sm.set(sk.LEARNING_ORIGINAL_COUNT, 1)
        sm.set(sk.LEARNING_CARD_MODES_DONE, {})
        sm.set(sk.LEARNING_CARD_RETRIES, {})
        sm.set(sk.LEARNING_ANSWERS, [])

        service = LearnService()
        bad = service.process_answer("wrong")
        assert bad.success and not bad.is_correct

        ok = service.process_answer("não me parece")
        assert ok.success and ok.is_correct

        answers = sm.get(sk.LEARNING_ANSWERS, [])
        assert answers[-1]["correct_answer"] == "não me parece"
        assert answers[-1]["mode"] == LearningMode.TYPE_EXAMPLE_GUIDED


def _card_level(service: LearnService, card_idx: int) -> Levels:
    """Read card level from session after deserialize."""
    state = service.session.get_state()
    assert state is not None
    raw = state.cards[card_idx]
    return service.session.deserialize_card(raw).level
