# Routes Refactoring Plan

## Executive Summary

This document outlines a comprehensive refactoring plan for the `src/routes/` module. The goal is to extract business logic into services, separate user paths (study vs review modes), and establish consistent organization for API endpoints.

**Current State:** 6 route files totaling ~1,800 lines with significant business logic embedded in route handlers.

**Target State:** Thin route handlers that delegate to focused services, with clear separation between learn mode, review mode, and API endpoints.

---

## Decisions Made

| Question | Decision | Rationale |
|----------|----------|-----------|
| Service granularity | **Independent** | Keep `LearnService` and `ReviewService` independent, no shared base class |
| Session state | **Simple** | No state machine pattern for now; leave as future iteration |
| URL structure | **`/learn/`** | Use `/learn/` for consistency with "learning" terminology |
| API versioning | **No** | No `/api/v1/` prefix needed yet |
| Index route | **Dedicated** | Move homepage to dedicated `routes/index.py` |

---

## Progress Tracking

| Phase | Status | Completed Date | Notes |
|-------|--------|----------------|-------|
| Phase 1: Service Layer Foundation | ✅ **COMPLETED** | 2025-11-28 | Created `CardSessionManager`, `CardStatistics` |
| Phase 2: Learn Service + Routes | ✅ **COMPLETED** | 2025-11-28 | Created `LearnService`, `learn_bp`, `index_bp` |
| Phase 3: Review Service + Routes | ✅ **COMPLETED** | 2025-11-28 | Created `ReviewService`, `review_bp` |
| Phase 4: API Restructuring | 🔲 Pending | - | - |
| Phase 5: Cleanup | 🔲 Pending | - | - |
| Phase 6: Index Route Extraction | ✅ **COMPLETED** | 2025-11-28 | Moved to `index_bp` in Phase 2 |

### Phase 1 Details
- ✅ Created `src/services/learning/__init__.py`
- ✅ Created `src/services/learning/card_session.py` - `CardSessionManager` class
- ✅ Created `src/services/learning/statistics.py` - `CardStatistics`, `LevelChange`, `AnswerResult`, `SessionStats`

### Phase 2 Details
- ✅ Created `src/services/learning/learn_service.py` - `LearnService` class with full session lifecycle
- ✅ Created `src/routes/index.py` - `index_bp` for homepage
- ✅ Created `src/routes/learn.py` - `learn_bp` for learn mode routes
- ✅ Updated `src/routes/__init__.py` - registered new blueprints
- ✅ Updated `src/routes/flashcard.py` - converted to legacy redirects
- ✅ Updated templates (`index.html`, `card.html`, `feedback.html`, `results.html`) to use new URLs
- ✅ Changed URL structure from `/study/` to `/learn/` as decided

### Phase 3 Details
- ✅ Created `src/services/learning/review_service.py` - `ReviewService` class for card browsing
- ✅ Created `src/routes/review.py` - `review_bp` for review mode routes
- ✅ Updated `src/routes/__init__.py` - registered `review_bp`
- ✅ Updated `src/routes/flashcard.py` - converted all remaining routes to redirects
- ✅ Updated templates for review mode URLs (`review.start`, `review.card`, `review.flip`, `review.navigate`)

---

## Table of Contents

1. [Current State Analysis](#1-current-state-analysis)
2. [Identified Problems](#2-identified-problems)
3. [Proposed Architecture](#3-proposed-architecture)
4. [Service Layer Design](#4-service-layer-design)
5. [Route Restructuring](#5-route-restructuring)
6. [Migration Plan](#6-migration-plan)
7. [Implementation Phases](#7-implementation-phases)

---

## 1. Current State Analysis

### File Metrics

| File | Lines | Primary Responsibility | Issues |
|------|-------|----------------------|--------|
| `flashcard.py` | 725 | Study & Review modes | ⚠️ **Critical** - massive business logic, mode forking |
| `api.py` | 425 | TTS, Cards, Language settings | Mixed concerns, inconsistent organization |
| `admin.py` | 344 | Database admin, debugging | OK - admin routes are acceptable |
| `settings.py` | 152 | User settings, spreadsheet config | Minor - some business logic |
| `test.py` | 89 | Testing endpoints | OK |
| `auth.py` | 57 | OAuth flow | ✅ **Good** - proper delegation to AuthManager |

### Code Flow Diagram (Current)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           flashcard.py                                   │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  start_learning() / start_review()                              │    │
│  │  ├── Read cards from Google Sheets                              │    │
│  │  ├── Filter/sort cards (different logic per mode)               │    │
│  │  ├── Serialize cards to session                                 │    │
│  │  └── Initialize session state                                   │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                              ↓                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  show_card(mode)                                                │    │
│  │  ├── if mode == "review": ...60+ lines of review logic...       │    │
│  │  ├── if mode == "study": ...80+ lines of study logic...         │    │
│  │  │   ├── Check if reviewing incorrect cards                     │    │
│  │  │   ├── Handle end of initial pass                             │    │
│  │  │   └── Manage card indices                                    │    │
│  │  └── Render template with mode-specific context                 │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                              ↓                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  process_answer() - Study mode only                             │    │
│  │  ├── Check if reviewing incorrect                               │    │
│  │  ├── Validate answer                                            │    │
│  │  ├── Update card statistics (level progression)                 │    │
│  │  ├── Track incorrect cards                                      │    │
│  │  └── Store answer history                                       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                              ↓                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  show_results() / end_session_early()                           │    │
│  │  ├── Calculate statistics (duplicated code)                     │    │
│  │  ├── Batch update to Google Sheets                              │    │
│  │  └── Clear session                                              │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Identified Problems

### 2.1 Business Logic in Routes (Critical)

**Location:** `flashcard.py` - nearly every route handler

**Examples:**
```python
# Card statistics update logic in process_answer()
card.cnt_shown += 1
card.last_shown = get_timestamp()
if is_correct:
    card.cnt_corr_answers += 1
    card.level = card.level.next_level()
else:
    card.level = card.level.previous_level()

# Answer validation logic
correct_answers = [current_card["word"].strip().lower()]
is_correct = user_answer in correct_answers
```

**Impact:**
- Routes are 100-200+ lines each
- Business logic changes require route modifications
- Difficult to unit test logic without HTTP context
- Violates Single Responsibility Principle

### 2.2 Mode Forking (Critical)

**Location:** `show_card()`, `show_feedback_with_mode()`

**Pattern:**
```python
if mode == "review":
    cards_key = sk.REVIEW_CARDS
    index_key = sk.REVIEW_CURRENT_INDEX
    # ... 50+ lines of review-specific logic
else:  # study mode
    cards_key = sk.LEARNING_CARDS
    index_key = sk.LEARNING_CURRENT_INDEX
    # ... 80+ lines of study-specific logic
```

**Impact:**
- Complex conditional logic
- Study and review modes have different state machines
- Adding new modes would require extensive modifications
- Hard to understand flow at a glance

### 2.3 Duplicated Code

**Location:** Multiple functions in `flashcard.py`

**Examples:**

1. **Session initialization** - duplicated in `start_learning()` and `start_review()`:
```python
# In start_learning()
cards_data = []
for card in cards:
    card_dict = card.model_dump()
    card_dict["last_shown"] = format_timestamp(card.last_shown)
    cards_data.append(card_dict)
sm.set(sk.LEARNING_CARDS, cards_data)
sm.set(sk.LEARNING_CURRENT_INDEX, 0)
# ... more initialization

# In start_review() - nearly identical
cards_data = []
for card in cards:
    card_dict = card.model_dump()
    card_dict["last_shown"] = format_timestamp(card.last_shown)
    cards_data.append(card_dict)
sm.set(sk.REVIEW_CARDS, cards_data)
sm.set(sk.REVIEW_CURRENT_INDEX, 0)
```

2. **Results calculation** - duplicated in `show_results()` and `end_session_early()`:
```python
# Same ~20 lines calculating statistics, batch updating, clearing session
```

### 2.4 Session State Complexity

**Location:** Scattered across `flashcard.py`

**Issue:** Multiple related session keys managed independently:
- `LEARNING_CARDS`, `LEARNING_CURRENT_INDEX`, `LEARNING_ANSWERS`
- `LEARNING_INCORRECT_CARDS`, `LEARNING_REVIEWING_INCORRECT`
- `LEARNING_ACTIVE_TAB`, `LEARNING_SHEET_GID`, `LEARNING_ORIGINAL_COUNT`
- Similar set for `REVIEW_*` keys

**Impact:**
- Easy to get state out of sync
- No encapsulation of state transitions
- Difficult to understand valid state combinations

### 2.5 Inconsistent API Organization

**Location:** `api.py`

**Current structure:**
```
/api/tts/status         - TTS status
/api/tts/speak          - Generate speech
/api/tts/speak-card     - Generate card speech
/api/cards/<tab>        - Get cards for listening
/api/language-settings  - GET/POST language settings
/api/language-settings/validate - Validate settings
```

**Problems:**
- Mixed concerns (TTS, cards, settings)
- Business logic for language settings validation
- No clear resource boundaries

---

## 3. Proposed Architecture

### 3.1 Target Structure

```
src/
├── routes/
│   ├── __init__.py           # Blueprint registration
│   ├── auth.py               # OAuth (unchanged)
│   ├── index.py              # Home page, login screen
│   ├── learn.py              # Learn mode routes (thin)
│   ├── review.py             # Review mode routes (thin)
│   ├── settings.py           # User settings routes
│   ├── admin.py              # Admin routes (unchanged)
│   ├── test.py               # Test routes (unchanged)
│   └── api/
│       ├── __init__.py       # API blueprint registration
│       ├── tts.py            # TTS endpoints
│       ├── cards.py          # Card management endpoints
│       └── language.py       # Language settings endpoints
│
├── services/
│   ├── __init__.py
│   ├── auth_manager.py       # OAuth (exists)
│   ├── learning/
│   │   ├── __init__.py
│   │   ├── learn_service.py  # Learn mode business logic
│   │   ├── review_service.py # Review mode business logic
│   │   ├── card_session.py   # Session state management
│   │   └── statistics.py     # Card statistics & level progression
│   ├── spreadsheet/
│   │   ├── __init__.py
│   │   ├── language_settings.py  # Language settings logic
│   │   └── validation.py     # Spreadsheet validation
│   └── tts_service.py        # TTS (exists)
```

### 3.2 Layered Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Routes Layer                              │
│  • HTTP request/response handling                                │
│  • Input validation (via Pydantic)                               │
│  • Authentication decorators                                     │
│  • Template rendering / JSON responses                           │
│  • ~10-30 lines per route handler                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Services Layer                             │
│  • Business logic                                                │
│  • State machine management                                      │
│  • Data transformation                                           │
│  • Orchestration of data layer calls                             │
│  • Unit testable without HTTP context                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Data Layer                                │
│  • gsheet.py - Google Sheets operations                          │
│  • database.py - SQLAlchemy models                               │
│  • session_manager.py - Session operations                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Service Layer Design

### 4.1 Learning Services Module

#### `services/learning/card_session.py`

Encapsulates session state management for card-based learning.

```python
"""Card session management for learning modes."""

from dataclasses import dataclass
from typing import Optional
from src.models import Card
from src.session_manager import SessionManager as sm, SessionKeys as sk


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

    Abstracts session key management and provides clean API
    for session operations.
    """

    def __init__(self, mode: str):
        """Initialize for specific mode ('study' or 'review')."""
        self.mode = mode
        self._setup_keys()

    def _setup_keys(self):
        """Configure session keys based on mode."""
        if self.mode == "study":
            self.cards_key = sk.LEARNING_CARDS
            self.index_key = sk.LEARNING_CURRENT_INDEX
            self.tab_key = sk.LEARNING_ACTIVE_TAB
            self.gid_key = sk.LEARNING_SHEET_GID
        else:  # review
            self.cards_key = sk.REVIEW_CARDS
            self.index_key = sk.REVIEW_CURRENT_INDEX
            self.tab_key = sk.REVIEW_ACTIVE_TAB
            self.gid_key = sk.REVIEW_SHEET_GID

    def initialize(self, cards: list[Card], tab_name: str, gid: int) -> None:
        """Initialize session with cards."""
        # Serialize cards for session storage
        cards_data = [self._serialize_card(card) for card in cards]
        sm.set(self.cards_key, cards_data)
        sm.set(self.index_key, 0)
        sm.set(self.tab_key, tab_name)
        sm.set(self.gid_key, gid)

    def get_state(self) -> Optional[SessionState]:
        """Get current session state or None if not initialized."""
        if not sm.has(self.cards_key) or not sm.has(self.index_key):
            return None
        return SessionState(
            cards=sm.get(self.cards_key),
            current_index=sm.get(self.index_key),
            active_tab=sm.get(self.tab_key),
            sheet_gid=sm.get(self.gid_key),
        )

    def get_current_card(self) -> Optional[dict]:
        """Get the current card."""
        state = self.get_state()
        if not state or state.current_index >= len(state.cards):
            return None
        return state.cards[state.current_index]

    def advance(self) -> bool:
        """Move to next card. Returns False if at end."""
        index = sm.get(self.index_key, 0)
        cards = sm.get(self.cards_key, [])
        if index >= len(cards) - 1:
            return False
        sm.set(self.index_key, index + 1)
        return True

    def update_card(self, card_index: int, card_data: dict) -> None:
        """Update a card in the session."""
        cards = sm.get(self.cards_key, [])
        if 0 <= card_index < len(cards):
            cards[card_index] = card_data
            sm.set(self.cards_key, cards)

    def clear(self) -> None:
        """Clear session data."""
        sm.clear_namespace(self.mode if self.mode == "learning" else "review")

    @staticmethod
    def _serialize_card(card: Card) -> dict:
        """Serialize Card object for session storage."""
        from src.utils import format_timestamp
        card_dict = card.model_dump()
        card_dict["last_shown"] = format_timestamp(card.last_shown)
        return card_dict
```

#### `services/learning/statistics.py`

Card statistics and level progression logic.

```python
"""Card statistics and level progression logic."""

from src.models import Card, Levels
from src.utils import get_timestamp


class CardStatistics:
    """Handles card statistics updates and level progression."""

    @staticmethod
    def check_answer(user_answer: str, correct_answer: str) -> bool:
        """Check if user answer matches correct answer."""
        return user_answer.strip().lower() == correct_answer.strip().lower()

    @staticmethod
    def update_on_answer(card: Card, is_correct: bool) -> tuple[Card, dict]:
        """Update card statistics based on answer.

        Returns:
            Tuple of (updated_card, level_change_info)
        """
        original_level = card.level.value

        card.cnt_shown += 1
        card.last_shown = get_timestamp()

        if is_correct:
            card.cnt_corr_answers += 1
            card.level = card.level.next_level()
        else:
            card.level = card.level.previous_level()

        level_change = {
            "from": original_level,
            "to": card.level.value,
            "is_correct": is_correct,
        }

        return card, level_change

    @staticmethod
    def calculate_session_stats(answers: list[dict]) -> dict:
        """Calculate statistics for a learning session."""
        total = len(answers)
        correct = sum(1 for a in answers if a.get("is_correct", False))
        review_answers = [a for a in answers if a.get("is_review", False)]

        return {
            "total_answered": total,
            "correct_answers": correct,
            "accuracy_percentage": int((correct / total * 100) if total > 0 else 0),
            "review_count": len(review_answers),
            "first_attempt_count": total - len(review_answers),
        }
```

#### `services/learning/learn_service.py`

Learn mode orchestration.

```python
"""Learn mode service - orchestrates learn session logic."""

import logging
from dataclasses import dataclass
from typing import Optional

from src.gsheet import read_card_set, update_spreadsheet
from src.models import Card
from src.config import config
from src.session_manager import SessionManager as sm, SessionKeys as sk

from .card_session import CardSessionManager
from .statistics import CardStatistics

logger = logging.getLogger(__name__)


@dataclass
class LearnSessionResult:
    """Result of initializing a learn session."""
    success: bool
    card_count: int = 0
    error: Optional[str] = None


@dataclass
class CardDisplayContext:
    """Context for displaying a card."""
    card: dict
    index: int
    total: int
    is_reviewing_incorrect: bool
    mode: str = "learn"


class LearnService:
    """Service for learn mode operations."""

    def __init__(self):
        self.session = CardSessionManager("learn")
        self.stats = CardStatistics()

    def start_session(
        self,
        tab_name: str,
        spreadsheet_id: str
    ) -> LearnSessionResult:
        """Start a new study session."""
        try:
            card_set = read_card_set(
                worksheet_name=tab_name,
                spreadsheet_id=spreadsheet_id
            )

            cards = card_set.get_cards_to_review(
                limit=config.max_cards_per_session,
                ignore_unshown=False
            )

            if not cards:
                return StudySessionResult(
                    success=False,
                    error="No cards due for review"
                )

            # Initialize session
            self.session.initialize(cards, tab_name, card_set.gid)

            # Initialize study-specific state
            sm.set(sk.LEARNING_ANSWERS, [])
            sm.set(sk.LEARNING_INCORRECT_CARDS, [])
            sm.set(sk.LEARNING_REVIEWING_INCORRECT, False)
            sm.set(sk.LEARNING_ORIGINAL_COUNT, len(cards))

            logger.info(f"Study session started: {len(cards)} cards from {tab_name}")

            return StudySessionResult(success=True, card_count=len(cards))

        except Exception as e:
            logger.error(f"Error starting learn session: {e}")
            return LearnSessionResult(success=False, error=str(e))

    def get_current_card_context(self) -> Optional[CardDisplayContext]:
        """Get context for displaying current card."""
        state = self.session.get_state()
        if not state:
            return None

        reviewing = sm.get(sk.LEARNING_REVIEWING_INCORRECT, False)
        index = state.current_index
        cards = state.cards

        # Check if we need to transition to reviewing incorrect
        if index >= len(cards) and not reviewing:
            incorrect_cards = sm.get(sk.LEARNING_INCORRECT_CARDS, [])
            if incorrect_cards:
                sm.set(sk.LEARNING_REVIEWING_INCORRECT, True)
                sm.set(sk.LEARNING_CURRENT_INDEX, 0)
                return self.get_current_card_context()  # Recursive call with new state
            return None  # Session complete

        # Get current card
        if reviewing:
            incorrect_indices = sm.get(sk.LEARNING_INCORRECT_CARDS, [])
            if index >= len(incorrect_indices):
                return None  # Review complete
            card_index = incorrect_indices[index]
            card = cards[card_index]
            total = len(incorrect_indices)
        else:
            card = cards[index]
            total = len(cards)

        card["is_review"] = reviewing

        return CardDisplayContext(
            card=card,
            index=index,
            total=total,
            is_reviewing_incorrect=reviewing,
        )

    def process_answer(self, user_answer: str) -> dict:
        """Process user's answer and return result."""
        context = self.get_current_card_context()
        if not context:
            return {"error": "No active session"}

        card = context.card
        is_correct = self.stats.check_answer(user_answer, card["word"])

        # Update card statistics
        card_obj = Card(**card)
        updated_card, level_change = self.stats.update_on_answer(card_obj, is_correct)

        # Store updated card in session
        reviewing = context.is_reviewing_incorrect
        if reviewing:
            incorrect_indices = sm.get(sk.LEARNING_INCORRECT_CARDS, [])
            card_index = incorrect_indices[context.index]
        else:
            card_index = context.index

        self.session.update_card(card_index, self.session._serialize_card(updated_card))

        # Track answer
        self._record_answer(card, user_answer, is_correct, reviewing, card_index)

        # Track incorrect for later review (first pass only)
        if not is_correct and not reviewing:
            self._track_incorrect(context.index)

        # Store level change for feedback
        sm.set(sk.LEARNING_LAST_LEVEL_CHANGE, level_change)

        return {
            "is_correct": is_correct,
            "level_change": level_change,
            "card": card,
        }

    def advance_to_next(self) -> bool:
        """Advance to next card. Returns False if session complete."""
        index = sm.get(sk.LEARNING_CURRENT_INDEX, 0)
        sm.set(sk.LEARNING_CURRENT_INDEX, index + 1)
        return True

    def end_session(self) -> dict:
        """End session and return results."""
        answers = sm.get(sk.LEARNING_ANSWERS, [])
        original_count = sm.get(sk.LEARNING_ORIGINAL_COUNT, len(answers))

        stats = self.stats.calculate_session_stats(answers)

        # Batch update to spreadsheet
        update_success = self._batch_update_cards()

        # Clear session
        sm.clear_namespace("learning")

        return {
            **stats,
            "answers": answers,
            "original_count": original_count,
            "update_successful": update_success,
        }

    def _record_answer(
        self,
        card: dict,
        user_answer: str,
        is_correct: bool,
        is_review: bool,
        card_index: int
    ) -> None:
        """Record answer in session history."""
        from src.utils import get_timestamp

        answers = sm.get(sk.LEARNING_ANSWERS, [])
        answers.append({
            "card_index": card_index,
            "word": card["word"],
            "translation": card["translation"],
            "user_answer": user_answer,
            "correct_answer": card["word"],
            "is_correct": is_correct,
            "timestamp": get_timestamp().isoformat(),
            "is_review": is_review,
        })
        sm.set(sk.LEARNING_ANSWERS, answers)

    def _track_incorrect(self, index: int) -> None:
        """Track incorrect answer for later review."""
        incorrect = sm.get(sk.LEARNING_INCORRECT_CARDS, [])
        incorrect.append(index)
        sm.set(sk.LEARNING_INCORRECT_CARDS, incorrect)

    def _batch_update_cards(self) -> bool:
        """Batch update modified cards to spreadsheet."""
        # Implementation from current batch_update_session_cards()
        # ...
        pass
```

#### `services/learning/review_service.py`

Review mode orchestration (simpler than study mode).

```python
"""Review mode service - orchestrates review session logic."""

import logging
from dataclasses import dataclass
from typing import Optional

from src.gsheet import read_card_set
from .card_session import CardSessionManager

logger = logging.getLogger(__name__)


@dataclass
class ReviewSessionResult:
    """Result of initializing a review session."""
    success: bool
    card_count: int = 0
    error: Optional[str] = None


@dataclass
class ReviewCardContext:
    """Context for displaying a review card."""
    card: dict
    index: int
    total: int
    mode: str = "review"


class ReviewService:
    """Service for review mode operations (browse all cards)."""

    def __init__(self):
        self.session = CardSessionManager("review")

    def start_session(
        self,
        tab_name: str,
        spreadsheet_id: str
    ) -> ReviewSessionResult:
        """Start a new review session with ALL cards."""
        try:
            card_set = read_card_set(
                worksheet_name=tab_name,
                spreadsheet_id=spreadsheet_id
            )

            cards = card_set.cards  # All cards, no filtering

            if not cards:
                return ReviewSessionResult(
                    success=False,
                    error="No cards in this set"
                )

            self.session.initialize(cards, tab_name, card_set.gid)

            logger.info(f"Review session started: {len(cards)} cards from {tab_name}")

            return ReviewSessionResult(success=True, card_count=len(cards))

        except Exception as e:
            logger.error(f"Error starting review session: {e}")
            return ReviewSessionResult(success=False, error=str(e))

    def get_current_card_context(self) -> Optional[ReviewCardContext]:
        """Get context for displaying current card."""
        state = self.session.get_state()
        if not state:
            return None

        card = state.cards[state.current_index]

        return ReviewCardContext(
            card=card,
            index=state.current_index,
            total=len(state.cards),
        )

    def navigate(self, direction: str) -> bool:
        """Navigate cards with wraparound."""
        state = self.session.get_state()
        if not state:
            return False

        total = len(state.cards)
        current = state.current_index

        if direction == "next":
            new_index = (current + 1) % total
        elif direction == "prev":
            new_index = (current - 1) % total
        else:
            return False

        from src.session_manager import SessionManager as sm
        sm.set(self.session.index_key, new_index)
        return True

    def end_session(self) -> None:
        """End review session."""
        self.session.clear()
```

### 4.2 Spreadsheet Services Module

#### `services/spreadsheet/language_settings.py`

```python
"""Language settings service."""

import logging
from pydantic import ValidationError
from src.models import SpreadsheetLanguages
from src.database import db

logger = logging.getLogger(__name__)


class LanguageSettingsService:
    """Service for language settings operations."""

    @staticmethod
    def get_settings(spreadsheet) -> SpreadsheetLanguages:
        """Get language settings for a spreadsheet."""
        properties = spreadsheet.get_properties()
        return properties.language

    @staticmethod
    def validate_settings(language_data: dict) -> tuple[bool, SpreadsheetLanguages | None, list]:
        """Validate language settings without saving.

        Returns:
            Tuple of (is_valid, settings_if_valid, validation_errors)
        """
        try:
            if isinstance(language_data, dict):
                settings = SpreadsheetLanguages.from_dict(language_data)
            else:
                settings = SpreadsheetLanguages(**language_data)

            warnings = []
            if not settings.is_valid_configuration():
                warnings.append("Language configuration has duplicate values")

            return True, settings, warnings

        except ValidationError as e:
            errors = [
                {
                    "field": error["loc"][0] if error["loc"] else "unknown",
                    "message": error["msg"],
                    "invalid_value": error.get("input"),
                }
                for error in e.errors()
            ]
            return False, None, errors

    @staticmethod
    def save_settings(
        spreadsheet,
        new_settings: SpreadsheetLanguages
    ) -> tuple[bool, str]:
        """Save language settings to spreadsheet.

        Returns:
            Tuple of (success, message)
        """
        try:
            # Business validation
            if not new_settings.is_valid_configuration():
                return False, "Language configuration cannot have duplicate values"

            # Get current for logging
            current_settings = spreadsheet.get_properties().language

            # Update
            properties = spreadsheet.get_properties()
            properties.language = new_settings
            spreadsheet.set_properties(properties)

            db.session.commit()

            logger.info(f"Language settings updated: {current_settings.to_dict()} -> {new_settings.to_dict()}")

            return True, "Language settings saved successfully"

        except Exception as e:
            logger.error(f"Error saving language settings: {e}")
            return False, str(e)
```

---

## 5. Route Restructuring

### 5.1 Learn Routes (`routes/learn.py`)

```python
"""Learn mode routes - thin handlers delegating to LearnService."""

from flask import Blueprint, redirect, render_template, request, url_for

from src.services.auth_manager import auth_manager
from src.services.learning.learn_service import LearnService

learn_bp = Blueprint("learn", __name__, url_prefix="/learn")


@learn_bp.route("/start/<tab_name>", methods=["POST"])
@auth_manager.require_auth
def start(tab_name: str):
    """Start a learn session."""
    user = auth_manager.user
    spreadsheet_id = user.get_active_spreadsheet_id()

    service = LearnService()
    result = service.start_session(tab_name, spreadsheet_id)

    if not result.success:
        return redirect(url_for("index.home"))

    return redirect(url_for("learn.card"))


@learn_bp.route("/card")
@auth_manager.require_auth
def card():
    """Display current learn card."""
    service = LearnService()
    context = service.get_current_card_context()

    if not context:
        return redirect(url_for("learn.results"))

    user = auth_manager.user

    return render_template(
        "card.html",
        card=context.card,
        index=context.index,
        total=context.total,
        reviewing=context.is_reviewing_incorrect,
        mode="learn",
        user_spreadsheet_id=user.get_active_spreadsheet_id(),
        # ... other template vars
    )


@learn_bp.route("/answer", methods=["POST"])
@auth_manager.require_auth
def answer():
    """Process answer."""
    user_answer = request.form.get("user_answer", "").strip()

    service = LearnService()
    result = service.process_answer(user_answer)

    if "error" in result:
        return redirect(url_for("index.home"))

    feedback_url = url_for(
        "learn.feedback",
        correct="yes" if result["is_correct"] else "no"
    )
    return redirect(feedback_url)


@learn_bp.route("/feedback/<correct>")
@auth_manager.require_auth
def feedback(correct: str):
    """Show feedback after answer."""
    service = LearnService()
    context = service.get_current_card_context()

    if not context:
        return redirect(url_for("index.home"))

    # Get level change from session
    from src.session_manager import SessionManager as sm, SessionKeys as sk
    level_change = sm.get(sk.LEARNING_LAST_LEVEL_CHANGE)
    if level_change:
        sm.remove(sk.LEARNING_LAST_LEVEL_CHANGE)

    return render_template(
        "feedback.html",
        card=context.card,
        correct=(correct == "yes"),
        reviewing=context.is_reviewing_incorrect,
        level_change=level_change,
        mode="learn",
        # ...
    )


@learn_bp.route("/next")
@auth_manager.require_auth
def next_card():
    """Move to next card."""
    service = LearnService()
    service.advance_to_next()
    return redirect(url_for("learn.card"))


@learn_bp.route("/results")
@auth_manager.require_auth
def results():
    """Show session results."""
    service = LearnService()
    stats = service.end_session()

    return render_template(
        "results.html",
        **stats,
        is_authenticated=True,
    )


@learn_bp.route("/end")
@auth_manager.require_auth
def end_early():
    """End session early."""
    return redirect(url_for("learn.results"))
```

### 5.2 Review Routes (`routes/review.py`)

```python
"""Review mode routes - thin handlers delegating to ReviewService."""

from flask import Blueprint, redirect, render_template, url_for

from src.services.auth_manager import auth_manager
from src.services.learning.review_service import ReviewService

review_bp = Blueprint("review", __name__, url_prefix="/review")


@review_bp.route("/start/<tab_name>")
@auth_manager.require_auth
def start(tab_name: str):
    """Start a review session."""
    user = auth_manager.user
    spreadsheet_id = user.get_active_spreadsheet_id()

    service = ReviewService()
    result = service.start_session(tab_name, spreadsheet_id)

    if not result.success:
        return redirect(url_for("flashcard.index"))

    return redirect(url_for("review.card"))


@review_bp.route("/card")
@auth_manager.require_auth
def card():
    """Display current review card."""
    service = ReviewService()
    context = service.get_current_card_context()

    if not context:
        return redirect(url_for("flashcard.index"))

    user = auth_manager.user

    return render_template(
        "card.html",
        card=context.card,
        index=context.index,
        total=context.total,
        reviewing=False,
        mode="review",
        user_spreadsheet_id=user.get_active_spreadsheet_id(),
    )


@review_bp.route("/nav/<direction>")
@auth_manager.require_auth
def navigate(direction: str):
    """Navigate between cards."""
    service = ReviewService()
    service.navigate(direction)
    return redirect(url_for("review.card"))


@review_bp.route("/end")
@auth_manager.require_auth
def end():
    """End review session."""
    service = ReviewService()
    service.end_session()
    return redirect(url_for("flashcard.index"))
```

### 5.3 API Routes Restructuring

#### `routes/api/__init__.py`

```python
"""API routes package."""

from flask import Blueprint

from .tts import tts_bp
from .cards import cards_bp
from .language import language_bp


api_bp = Blueprint("api", __name__, url_prefix="/api")

# Register sub-blueprints
api_bp.register_blueprint(tts_bp)
api_bp.register_blueprint(cards_bp)
api_bp.register_blueprint(language_bp)
```

#### `routes/api/tts.py`

```python
"""TTS API endpoints."""

from flask import Blueprint, jsonify, request

from src.config import config
from src.tts_service import TTSService

tts_bp = Blueprint("tts", __name__, url_prefix="/tts")
tts_service = TTSService()


@tts_bp.route("/status")
def status():
    """Get TTS service status."""
    # ... existing logic, no changes needed


@tts_bp.route("/speak", methods=["POST"])
def speak():
    """Generate speech for text."""
    # ... existing logic


@tts_bp.route("/speak-card", methods=["POST"])
def speak_card():
    """Generate speech for card content."""
    # ... existing logic
```

#### `routes/api/language.py`

```python
"""Language settings API endpoints."""

from flask import Blueprint, jsonify, request

from src.services.auth_manager import auth_manager
from src.services.spreadsheet.language_settings import LanguageSettingsService

language_bp = Blueprint("language", __name__, url_prefix="/language-settings")


@language_bp.route("/", methods=["GET"])
@auth_manager.require_auth_api
def get_settings():
    """Get current language settings."""
    user = auth_manager.user
    spreadsheet = user.get_active_spreadsheet()

    if not spreadsheet:
        return jsonify({"success": False, "error": "No active spreadsheet"}), 404

    service = LanguageSettingsService()
    settings = service.get_settings(spreadsheet)

    return jsonify({
        "success": True,
        "language_settings": settings.to_dict(),
    })


@language_bp.route("/", methods=["POST"])
@auth_manager.require_auth_api
def save_settings():
    """Save language settings."""
    user = auth_manager.user
    spreadsheet = user.get_active_spreadsheet()

    if not spreadsheet:
        return jsonify({"success": False, "error": "No active spreadsheet"}), 404

    data = request.get_json()
    language_data = data.get("language_settings") or data.get("language")

    if not language_data:
        return jsonify({"success": False, "error": "Language settings required"}), 400

    service = LanguageSettingsService()

    # Validate
    is_valid, settings, errors = service.validate_settings(language_data)
    if not is_valid:
        return jsonify({"success": False, "validation_errors": errors}), 400

    # Save
    success, message = service.save_settings(spreadsheet, settings)

    if not success:
        return jsonify({"success": False, "error": message}), 400

    return jsonify({
        "success": True,
        "message": message,
        "language_settings": settings.to_dict(),
    })


@language_bp.route("/validate", methods=["POST"])
def validate():
    """Validate language settings without saving."""
    data = request.get_json()
    language_data = data.get("language_settings") or data.get("language")

    if not language_data:
        return jsonify({"success": False, "error": "Language settings required"}), 400

    service = LanguageSettingsService()
    is_valid, settings, errors_or_warnings = service.validate_settings(language_data)

    if is_valid:
        return jsonify({
            "success": True,
            "valid": True,
            "language_settings": settings.to_dict(),
            "warnings": errors_or_warnings,
        })
    else:
        return jsonify({
            "success": True,
            "valid": False,
            "validation_errors": errors_or_warnings,
        })
```

---

## 6. Migration Plan

### 6.1 URL Mapping Changes

| Current URL | New URL | Notes |
|-------------|---------|-------|
| `POST /start/<tab>` | `POST /learn/start/<tab>` | Learn mode |
| `GET /review/<tab>` | `GET /review/start/<tab>` | Review mode |
| `GET /card` | `GET /learn/card` or `GET /review/card` | Mode-specific |
| `GET /card/review` | `GET /review/card` | Simplified |
| `POST /answer` | `POST /learn/answer` | Learn only |
| `GET /review/nav/<dir>` | `GET /review/nav/<dir>` | Unchanged |
| `GET /feedback/<correct>` | `GET /learn/feedback/<correct>` | Learn only |
| `GET /results` | `GET /learn/results` | Learn only |
| `GET /next` | `GET /learn/next` | Learn only |
| `GET /end-session` | `GET /learn/end` or `GET /review/end` | Mode-specific |

### 6.2 Backward Compatibility

For a smooth transition, we can keep old routes as redirects during a transition period:

```python
# In flashcard.py (temporary, during migration)
@flashcard_bp.route("/start/<tab_name>", methods=["POST"])
def legacy_start_learning(tab_name: str):
    """Legacy route - redirects to new learn blueprint."""
    return redirect(url_for("learn.start", tab_name=tab_name), code=307)
```

### 6.3 Template Updates

Templates need minimal changes - mainly URL generation:

```html
<!-- Before -->
<form action="{{ url_for('flashcard.process_answer') }}" method="POST">

<!-- After -->
<form action="{{ url_for('learn.answer') }}" method="POST">
```

---

## 7. Implementation Phases

### Phase 1: Service Layer Foundation (Low Risk)
**Duration:** 1-2 days

1. Create `services/learning/` directory structure
2. Implement `CardSessionManager` class
3. Implement `CardStatistics` class
4. Write unit tests for new services
5. **No route changes yet**

### Phase 2: Learn Service (Medium Risk)
**Duration:** 2-3 days

1. Implement `LearnService` class
2. Create `routes/learn.py` with new routes
3. Register new blueprint
4. Add legacy redirects in `flashcard.py`
5. Update templates to use new URLs
6. Integration testing

### Phase 3: Review Service (Low Risk) ✅
**Duration:** 1 day
**Completed:** 2025-11-28

1. ✅ Implement `ReviewService` class
2. ✅ Create `routes/review.py` with new routes
3. ✅ Register new blueprint
4. ✅ Add legacy redirects
5. ✅ Update templates

### Phase 4: API Restructuring (Low Risk)
**Duration:** 1 day

1. Create `routes/api/` directory
2. Split `api.py` into `tts.py`, `cards.py`, `language.py`
3. Implement `LanguageSettingsService`
4. Update API blueprint registration

### Phase 5: Cleanup (Low Risk)
**Duration:** 1 day

1. Remove deprecated code from `flashcard.py`
2. Remove legacy redirects (after verification)
3. Update documentation
4. Final testing

### Phase 6: Index Route Extraction (Optional)
**Duration:** 0.5 day

1. Move index route from `flashcard.py` to `routes/index.py`
2. Keep `flashcard_bp` for any remaining shared routes

---

## Appendix A: Files Changed Summary

### New Files

```
src/services/learning/__init__.py
src/services/learning/card_session.py
src/services/learning/statistics.py
src/services/learning/learn_service.py
src/services/learning/review_service.py
src/services/spreadsheet/__init__.py
src/services/spreadsheet/language_settings.py
src/routes/learn.py
src/routes/review.py
src/routes/api/__init__.py
src/routes/api/tts.py
src/routes/api/cards.py
src/routes/api/language.py
```

### Modified Files

```
src/routes/__init__.py          # Register new blueprints
src/routes/flashcard.py         # Remove migrated code, keep index
src/routes/api.py               # Delete after migration
templates/card.html             # Update URLs
templates/feedback.html         # Update URLs
templates/results.html          # Update URLs
templates/index.html            # Update URLs
```

### Deleted Files (After Migration)

```
src/routes/api.py               # Replaced by api/ directory
```

---

## Appendix B: Testing Strategy

### Unit Tests (New)

```python
# tests/services/learning/test_statistics.py
def test_check_answer_correct():
    assert CardStatistics.check_answer("Olá", "olá") == True
    assert CardStatistics.check_answer("  Olá  ", "olá") == True

def test_check_answer_incorrect():
    assert CardStatistics.check_answer("Ola", "olá") == False

def test_update_on_correct_answer():
    card = Card(id=1, word="test", translation="test", ...)
    updated, change = CardStatistics.update_on_answer(card, is_correct=True)
    assert updated.level.value == 1
    assert change["is_correct"] == True
```

### Integration Tests

```python
# tests/routes/test_learn.py
def test_learn_flow(client, authenticated_user):
    # Start session
    response = client.post("/learn/start/Vocabulary")
    assert response.status_code == 302

    # View card
    response = client.get("/learn/card")
    assert response.status_code == 200
    assert b"word" in response.data

    # Submit answer
    response = client.post("/learn/answer", data={"user_answer": "test"})
    assert response.status_code == 302
```

---

## Appendix C: Risk Assessment

| Change | Risk Level | Mitigation |
|--------|------------|------------|
| Service layer extraction | Low | Services are new code, no breaking changes |
| New route blueprints | Medium | Legacy redirects maintain compatibility |
| URL changes | Medium | Update templates in same phase as routes |
| Removing old routes | Low | Only after thorough testing |
| API restructuring | Low | URLs remain same, just different files |

---

## Decision Points ~~for Review~~ RESOLVED

All decision points have been resolved. See "Decisions Made" section at the top of this document.
