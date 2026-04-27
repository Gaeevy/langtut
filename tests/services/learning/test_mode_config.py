"""Tests for learning mode configuration helpers."""

import random

from app.models import Levels
from app.services.learning.mode_config import (
    LearningMode,
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

    def test_levels_6_7_guided_level_8_write_example(self) -> None:
        assert get_pipeline(6) == [LearningMode.TYPE_EXAMPLE_GUIDED]
        assert get_pipeline(7) == [LearningMode.TYPE_EXAMPLE_GUIDED]
        assert get_pipeline(8) == [LearningMode.WRITE_EXAMPLE]

    def test_level_5_still_type_answer(self) -> None:
        assert get_pipeline(5) == [LearningMode.TYPE_ANSWER]

    def test_enum_levels_match_int_pipeline(self) -> None:
        assert get_pipeline(Levels.LEVEL_6) == [LearningMode.TYPE_EXAMPLE_GUIDED]
        assert get_pipeline(Levels.LEVEL_8) == [LearningMode.WRITE_EXAMPLE]
