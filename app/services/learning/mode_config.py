"""Learning mode configuration and task queue building.

Defines the available question modes, per-level pipelines, and helpers
for generating mode-specific data (distractors, shuffled tiles).
"""

import random
from enum import StrEnum

from app.models import Card, Levels


class LearningMode(StrEnum):
    """Available question modes, ordered from easiest to hardest."""

    PICK_TRANSLATION = "pick_translation"
    PICK_ONE = "pick_one"
    BUILD_SENTENCE = "build_sentence"
    BUILD_WORD = "build_word"
    TYPE_ANSWER = "type_answer"
    WRITE_EXAMPLE = "write_example"


# Global mode order -- queue is always built in this order so easier modes come first.
GLOBAL_MODE_ORDER: list[LearningMode] = [
    LearningMode.PICK_TRANSLATION,
    LearningMode.PICK_ONE,
    LearningMode.BUILD_SENTENCE,
    LearningMode.BUILD_WORD,
    LearningMode.TYPE_ANSWER,
    LearningMode.WRITE_EXAMPLE,
]

# Maps the *minimum* level at which each pipeline applies.
# The highest-matching threshold wins.
# Level 0-2 -> pick_translation + pick_one + build_sentence
# Level 3   -> build_sentence + build_word + type_answer
# Level 4   -> build_word + type_answer
# Level 5-7 -> type_answer only
# Level 8   -> write_example only
LEVEL_PIPELINES: dict[int, list[LearningMode]] = {
    0: [
        LearningMode.PICK_TRANSLATION,
        LearningMode.PICK_ONE,
        LearningMode.BUILD_SENTENCE,
    ],
    3: [LearningMode.BUILD_SENTENCE, LearningMode.BUILD_WORD, LearningMode.TYPE_ANSWER],
    4: [LearningMode.BUILD_WORD, LearningMode.TYPE_ANSWER],
    5: [LearningMode.TYPE_ANSWER],
    8: [LearningMode.WRITE_EXAMPLE],
}

# Number of options shown in pick_one mode (including correct answer)
PICK_ONE_OPTIONS_COUNT = 4


def get_pipeline(level: Levels | int) -> list[LearningMode]:
    """Return the mode pipeline for a given card level.

    Args:
        level: Card level (Levels enum or int)

    Returns:
        Ordered list of LearningMode values for this level
    """
    level_int = level.value if isinstance(level, Levels) else int(level)
    # Find highest threshold that is <= card level
    matching = [threshold for threshold in LEVEL_PIPELINES if threshold <= level_int]
    threshold = max(matching)
    return LEVEL_PIPELINES[threshold]


def build_task_queue(cards: list[Card]) -> list[dict]:
    """Build an ordered task queue for a session.

    Tasks are grouped by mode (all pick_one tasks, then all build_sentence, etc.)
    so the session proceeds in rounds. Within each mode-round, card order is shuffled.

    Args:
        cards: List of Card objects in the session

    Returns:
        List of task dicts: [{"card_idx": int, "mode": str}, ...]
    """
    queue: list[dict] = []
    for mode in GLOBAL_MODE_ORDER:
        cards_for_mode = [i for i, card in enumerate(cards) if mode in get_pipeline(card.level)]
        random.shuffle(cards_for_mode)
        for card_idx in cards_for_mode:
            queue.append({"card_idx": card_idx, "mode": mode})
    return queue


def generate_distractors(card: Card, all_cards: list[dict], count: int = 3) -> list[str]:
    """Generate wrong-answer word options for pick_one mode.

    Picks `count` target-language words from other cards in the session.
    Falls back to placeholder strings if there aren't enough distinct cards.

    Args:
        card: The correct card
        all_cards: All card dicts in the session (used as distractor pool)
        count: Number of distractors to generate

    Returns:
        List of distractor word strings (length == count)
    """
    correct = card.word.strip().lower()
    pool = [c["word"] for c in all_cards if c["word"].strip().lower() != correct]
    random.shuffle(pool)
    distractors = pool[:count]

    # Pad if pool is too small (unlikely, but safe)
    while len(distractors) < count:
        distractors.append(f"option {len(distractors) + 1}")

    return distractors


def shuffle_words(sentence: str) -> list[str]:
    """Shuffle the words of a sentence for build_sentence mode.

    Ensures the result is never in the original order (when possible).

    Args:
        sentence: The example sentence to shuffle

    Returns:
        List of word strings in shuffled order
    """
    words = sentence.split()
    if len(words) <= 1:
        return words
    shuffled = words.copy()
    attempts = 0
    while shuffled == words and attempts < 10:
        random.shuffle(shuffled)
        attempts += 1
    return shuffled


def sort_letters(word: str) -> list[str]:
    """Return the letters of a word sorted alphabetically for build_word mode.

    Alphabetical order removes the visual positional giveaway while remaining
    predictable and easy to scan.

    Args:
        word: The target word

    Returns:
        List of letter strings sorted A-Z (case-insensitive key, original case preserved)
    """
    return sorted(word, key=lambda c: c.lower())


def build_options(card: Card, all_cards: list[dict]) -> list[str]:
    """Build the full list of options for pick_one mode (correct word + distractors), shuffled.

    The prompt shows the translation; the options are target-language words.

    Args:
        card: The correct card
        all_cards: All card dicts in the session

    Returns:
        Shuffled list of PICK_ONE_OPTIONS_COUNT word strings
    """
    distractors = generate_distractors(card, all_cards, count=PICK_ONE_OPTIONS_COUNT - 1)
    options = [card.word, *distractors]
    random.shuffle(options)
    return options


def generate_translation_distractors(
    card: Card, all_cards: list[dict], count: int = 3
) -> list[str]:
    """Generate wrong translation options for pick_translation mode.

    Picks `count` translations from other cards in the session.

    Args:
        card: The correct card
        all_cards: All card dicts in the session (used as distractor pool)
        count: Number of distractors to generate

    Returns:
        List of distractor translation strings (length == count)
    """
    correct = card.translation.strip().lower()
    pool = [c["translation"] for c in all_cards if c["translation"].strip().lower() != correct]
    random.shuffle(pool)
    distractors = pool[:count]

    while len(distractors) < count:
        distractors.append(f"option {len(distractors) + 1}")

    return distractors


def build_translation_options(card: Card, all_cards: list[dict]) -> list[str]:
    """Build options for pick_translation (correct translation + distractors), shuffled.

    The prompt shows the target-language word; options are translations.

    Args:
        card: The correct card
        all_cards: All card dicts in the session

    Returns:
        Shuffled list of PICK_ONE_OPTIONS_COUNT translation strings
    """
    distractors = generate_translation_distractors(
        card, all_cards, count=PICK_ONE_OPTIONS_COUNT - 1
    )
    options = [card.translation, *distractors]
    random.shuffle(options)
    return options
