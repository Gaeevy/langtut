"""
Data models for the application.

This module contains Pydantic models for representing data structures
in the application, such as language cards and tab collections.
"""
import random
from pydantic import BaseModel, computed_field
from typing import List, Optional
from enum import Enum
from datetime import datetime, timedelta


NEVER_SHOWN = datetime(1970, 1, 1)  # Unix epoch start date


class Levels(Enum):
    LEVEL_0 = 0
    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3
    LEVEL_4 = 4
    LEVEL_5 = 5
    LEVEL_6 = 6
    LEVEL_7 = 7

    def next_level(self):
        """Get the next proficiency level."""
        return Levels(self.value + 1) if self.value < 7 else Levels.LEVEL_7

    def previous_level(self):
        """Get the previous proficiency level."""
        return Levels(self.value - 1) if self.value > 0 else Levels.LEVEL_0


days_to_review = {
    Levels.LEVEL_0: 0,
    Levels.LEVEL_1: 3,
    Levels.LEVEL_2: 7,
    Levels.LEVEL_3: 14,
    Levels.LEVEL_4: 30,
    Levels.LEVEL_5: 60,
    Levels.LEVEL_6: 90,
    Levels.LEVEL_7: 120,
}


class Card(BaseModel):
    """
    Represents a language learning flashcard.
    
    Attributes:
        id: Unique identifier for the card
        word: The word in the language being learned
        translation: The translation of the word
        equivalent: Alternative translation or related expressions
        example: Example sentence using the word
        example_translation: Translation of the example sentence
        cnt_shown: Counter for how many times the card was shown
        cnt_corr_answers: Counter for correct answers
        level: Proficiency level of the user for this card
        last_shown: Timestamp of when the card was last shown
    """
    id: int
    word: str
    translation: str
    equivalent: str
    example: str
    example_translation: str
    cnt_shown: int = 0
    cnt_corr_answers: int = 0
    level: Levels = Levels.LEVEL_0
    last_shown: datetime = NEVER_SHOWN
    
    @computed_field
    def next_review(self) -> datetime:
        """Calculate when this card should be reviewed next based on its level."""
        return self.last_shown + timedelta(days=days_to_review[self.level])
    
    @computed_field
    def seconds_to_next_review(self) -> int:
        """Calculate seconds until the next review is due."""
        time_delta = self.next_review - datetime.now()
        return int(time_delta.total_seconds())
    
    @computed_field
    def is_delayed(self) -> bool:
        """Check if this card is overdue for review."""
        return datetime.now() > self.next_review


# Pydantic model for tabs
class CardSet(BaseModel):
    """
    Represents a collection of cards (a tab in the spreadsheet).
    
    Attributes:
        name: The name of the tab
        cards: List of Card objects in this tab
    """
    name: str
    cards: List[Card] = []

    @property
    def card_count(self) -> int:
        """Returns the number of cards in this tab."""
        return len(self.cards)

    @property
    def average_level(self) -> float:
        """Calculates the average proficiency level across all cards."""
        if not self.cards:
            return 0.0
        return round(sum(card.level.value for card in self.cards) / len(self.cards), 1)

    def get_cards_to_review(self, limit: int | None = None) -> List[Card]:
        """Returns the number of cards that are due for review."""
        cards_to_review = [card for card in self.cards if card.is_delayed]
        sorted_cards = sorted(cards_to_review, key=lambda card: card.seconds_to_next_review)
        cards = sorted_cards[:limit] if limit else sorted_cards
        random.shuffle(cards)
        return cards