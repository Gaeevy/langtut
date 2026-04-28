"""Tests for learning mode configuration helpers."""

import random

from app.models import Card, Levels
from app.services.learning.mode_config import (
    GLOBAL_MODE_ORDER,
    LearningMode,
    build_task_queue,
    get_pipeline,
    sort_letters,
)


class TestSortLettersBuildWord:
    """build_word tiles: diacritic-ambiguous letters keep canonical order."""

    def test_nao_me_parece_keeps_tilde_a_before_plain_a(self) -> None:
        word = "não me parece"
        random.seed(42)
        for _ in range(40):
            tiles = sort_letters(word)
            idx_tilde = tiles.index("ã")
            idx_plain = tiles.index("a")
            assert idx_tilde < idx_plain

    def test_tilde_a_sequence_order(self) -> None:
        tiles = sort_letters("ãa")
        assert tiles.index("ã") < tiles.index("a")

    def test_shuffle_is_permutation(self) -> None:
        tiles = sort_letters("ab")
        assert sorted(tiles) == ["a", "b"]

    def test_c_cedilla_block_order(self) -> None:
        word = "caça"
        for _ in range(30):
            tiles = sort_letters(word)
            assert tiles.index("c") < tiles.index("ç")


class TestLevelPipelines:
    """Per-level mode pipelines."""

    def test_level_4_build_word_guided_type_answer(self) -> None:
        assert get_pipeline(4) == [
            LearningMode.BUILD_WORD,
            LearningMode.TYPE_EXAMPLE_GUIDED,
            LearningMode.TYPE_ANSWER,
        ]

    def test_levels_5_6_7_guided_level_8_write_example(self) -> None:
        assert get_pipeline(5) == [LearningMode.TYPE_ANSWER, LearningMode.TYPE_EXAMPLE_GUIDED]
        assert get_pipeline(6) == [LearningMode.TYPE_ANSWER, LearningMode.TYPE_EXAMPLE_GUIDED]
        assert get_pipeline(7) == [LearningMode.TYPE_EXAMPLE_GUIDED]
        assert get_pipeline(8) == [LearningMode.WRITE_EXAMPLE]

    def test_enum_levels_match_int_pipeline(self) -> None:
        assert get_pipeline(Levels.LEVEL_5) == [
            LearningMode.TYPE_ANSWER,
            LearningMode.TYPE_EXAMPLE_GUIDED,
        ]
        assert get_pipeline(Levels.LEVEL_6) == [
            LearningMode.TYPE_ANSWER,
            LearningMode.TYPE_EXAMPLE_GUIDED,
        ]
        assert get_pipeline(Levels.LEVEL_7) == [LearningMode.TYPE_EXAMPLE_GUIDED]
        assert get_pipeline(Levels.LEVEL_8) == [LearningMode.WRITE_EXAMPLE]


class TestBuildTaskQueue:
    """Session queue groups tasks by GLOBAL_MODE_ORDER (rounds)."""

    def test_queue_modes_appear_in_global_order_when_mixed_levels(self) -> None:
        random.seed(0)
        cards = [
            Card(
                id=1,
                word="a",
                translation="b",
                equivalent="",
                example="ex",
                example_translation="",
                level=Levels.LEVEL_0,
            ),
            Card(
                id=2,
                word="c",
                translation="d",
                equivalent="",
                example="ey",
                example_translation="",
                level=Levels.LEVEL_8,
            ),
        ]
        q = build_task_queue(cards)
        first_index: dict[LearningMode, int] = {}
        for i, task in enumerate(q):
            mode = task["mode"]
            if not isinstance(mode, LearningMode):
                mode = LearningMode(mode)
            if mode not in first_index:
                first_index[mode] = i
        order = list(GLOBAL_MODE_ORDER)
        for i in range(len(order) - 1):
            earlier, later = order[i], order[i + 1]
            if earlier in first_index and later in first_index:
                assert first_index[earlier] < first_index[later]
