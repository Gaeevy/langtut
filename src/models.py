"""
Data models for the application.

This module contains Pydantic models for representing data structures
in the application, such as language cards and tab collections.
"""

import json
import random
from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel, Field, computed_field

NEVER_SHOWN = datetime(1970, 1, 1)  # Unix epoch start date


class Levels(int, Enum):
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
    Levels.LEVEL_1: 2,
    Levels.LEVEL_2: 5,
    Levels.LEVEL_3: 9,
    Levels.LEVEL_4: 15,
    Levels.LEVEL_5: 25,
    Levels.LEVEL_6: 40,
    Levels.LEVEL_7: 60,
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
        gid: The permanent sheet ID (numeric)
        cards: List of Card objects in this tab
    """

    name: str
    gid: int  # Permanent sheet ID from Google Sheets
    cards: list[Card] = []

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

    def cards_to_review(self, ignore_unshown: bool) -> list[Card]:
        """Returns the list of cards that are due for review."""
        if ignore_unshown:
            return [card for card in self.cards if card.is_delayed and card.cnt_shown > 0]
        else:
            return [card for card in self.cards if card.is_delayed]

    def get_cards_to_review(
        self, limit: int | None = None, ignore_unshown: bool = False
    ) -> list[Card]:
        """Returns the number of cards that are due for review."""
        cards_to_review = self.cards_to_review(ignore_unshown)
        sorted_cards = sorted(cards_to_review, key=lambda card: card.seconds_to_next_review)
        cards = sorted_cards[:limit] if limit else sorted_cards
        random.shuffle(cards)
        return cards


class SpreadsheetLanguages(BaseModel):
    """
    Language settings for spreadsheet learning configuration.

    Attributes:
        original: Language code being learned FROM (e.g., 'ru' for Russian)
        target: Language code being learned TO (e.g., 'pt' for Portuguese)
        hint: Language code for interface/hints (e.g., 'en' for English)
    """

    original: str = Field(
        default='ru', description='Language being learned from', min_length=2, max_length=5
    )
    target: str = Field(
        default='pt', description='Language being learned to', min_length=2, max_length=5
    )
    hint: str = Field(
        default='en', description='Interface/hint language', min_length=2, max_length=5
    )

    @classmethod
    def get_default(cls) -> 'SpreadsheetLanguages':
        """Get default language settings."""
        return cls()

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary for backward compatibility."""
        return {'original': self.original, 'target': self.target, 'hint': self.hint}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> 'SpreadsheetLanguages':
        """Create from dictionary for backward compatibility."""
        return cls(
            original=data.get('original', 'ru'),
            target=data.get('target', 'pt'),
            hint=data.get('hint', 'en'),
        )

    def is_valid_configuration(self) -> bool:
        """Check if the language configuration is valid (no duplicates, proper codes)."""
        # Check that all languages are different (optional validation)
        languages = [self.original, self.target, self.hint]
        return len(set(languages)) == len(languages)  # No duplicates

    def update_from_dict(self, updates: dict[str, str]) -> 'SpreadsheetLanguages':
        """Create a new instance with updated values from dictionary."""
        current_dict = self.to_dict()
        current_dict.update(updates)
        return self.from_dict(current_dict)


class UserSpreadsheetProperty(BaseModel):
    """
    Properties for UserSpreadsheet configuration.

    Stores language settings and other user-specific spreadsheet configurations.
    """

    language: SpreadsheetLanguages = Field(default_factory=SpreadsheetLanguages.get_default)

    def to_db_string(self) -> str:
        """Convert properties to JSON string for database storage."""
        return json.dumps(self.model_dump())

    @classmethod
    def from_db_string(cls, value: str | None) -> 'UserSpreadsheetProperty':
        """Create UserSpreadsheetProperty from database JSON string."""
        if not value:
            return cls()  # Return default values

        try:
            data = json.loads(value)

            # Handle backward compatibility - if language is a dict, convert it
            if 'language' in data and isinstance(data['language'], dict):
                data['language'] = SpreadsheetLanguages.from_dict(data['language'])

            return cls(**data)
        except (json.JSONDecodeError, TypeError, ValueError):
            # If JSON parsing fails, return default values
            return cls()

    @classmethod
    def get_default(cls) -> 'UserSpreadsheetProperty':
        """Get default properties."""
        return cls()

    def get_language_dict(self) -> dict[str, str]:
        """Get language settings as dictionary for backward compatibility."""
        return self.language.to_dict()

    def set_language_dict(self, language_dict: dict[str, str]) -> None:
        """Set language settings from dictionary for backward compatibility."""
        self.language = SpreadsheetLanguages.from_dict(language_dict)
