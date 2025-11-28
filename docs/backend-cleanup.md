# Backend Cleanup & Modernization Guide

**Version:** 1.0
**Last Updated:** 2024
**Status:** Planning Document

---

## Table of Contents

1. [Overview](#overview)
2. [Current Architecture Issues](#current-architecture-issues)
3. [Phase 1: Session Management Cleanup](#phase-1-session-management-cleanup)
4. [Phase 2: State API Layer](#phase-2-state-api-layer)
5. [Phase 3: Service Layer Extraction](#phase-3-service-layer-extraction)
6. [Phase 4: Database Optimization](#phase-4-database-optimization)
7. [Testing Strategy](#testing-strategy)
8. [Migration Guide](#migration-guide)

---

## Overview

### Goals

1. **Clean Session Management** - Single, consistent pattern for all session access
2. **API-First State Sync** - Support hybrid client/server state management
3. **Service Layer** - Separate business logic from HTTP routing
4. **Type Safety** - Comprehensive Pydantic models for all data
5. **Maintainability** - Clear patterns that scale

### Principles

- **No Breaking Changes** - Incremental refactoring, always deployable
- **Backward Compatible** - Old code continues working during migration
- **Test Coverage** - Add tests before refactoring
- **Documentation** - Document patterns as you implement

### Timeline Estimate

- **Phase 1:** 2-3 hours (Session cleanup)
- **Phase 2:** 4-5 hours (API layer)
- **Phase 3:** 6-8 hours (Service layer)
- **Phase 4:** 2-3 hours (Database review)

**Total:** ~15-20 hours of focused development

---

## Current Architecture Issues

### Issue 1: Phantom Session Parameters

**Problem:** Functions accept `session_obj` parameter but never use it.

```python
# ❌ Current Code (user_manager.py)
def get_user_spreadsheet_id(session_obj):
    """session_obj is NEVER used!"""
    user = get_current_user()  # Uses SessionManager internally
    if not user:
        return None
    active_spreadsheet = get_user_active_spreadsheet(user.id)
    return active_spreadsheet.spreadsheet_id if active_spreadsheet else None

# ❌ Call sites pass unused parameter (flashcard.py)
user_spreadsheet_id = get_user_spreadsheet_id(session)
```

**Why This Is Bad:**
- Misleading API - developers think session is being threaded through
- False dependency - function appears to need session but uses global state
- Testing complexity - unclear what needs to be mocked
- Code smell - indicates incomplete refactoring

**Impact:** ~5 functions across `user_manager.py`, ~15 call sites across route files

---

### Issue 2: Inconsistent State Access Patterns

**Problem:** Mix of direct session access, SessionManager, and database queries.

```python
# Pattern A: SessionManager (Modern)
user_id = sm.get(sk.USER_ID)

# Pattern B: Helper function with phantom parameter (Legacy)
spreadsheet_id = get_user_spreadsheet_id(session)  # Doesn't use session!

# Pattern C: Direct session access (Forbidden but exists in old code)
cards = session.get('learning.cards')  # Should use SessionManager
```

**Why This Is Bad:**
- No single source of truth
- Can't grep for all state access
- Different patterns in different files
- Hard to understand data flow

---

### Issue 3: No State Persistence for Listening Mode

**Problem:** Listening mode state lives only in JavaScript, lost on page reload.

```javascript
// listening.js - All state lost on navigation!
this.currentSession = 'Common Words';
this.isPlaying = true;
this.currentCardIndex = 5;
this.cards = [...];  // 50 cards
```

**User Impact:**
1. User starts listening mode (50 cards)
2. Gets to card 20
3. Accidentally navigates away
4. Returns to listening mode
5. **State lost** - starts from card 1 again ❌

**Why This Is Bad:**
- Poor UX - can't resume listening sessions
- No sync between client/server state
- Race conditions with async operations
- Ghost audio continues playing after navigation

---

### Issue 4: No Clear API Boundaries

**Problem:** Routes handle business logic directly, no API layer for state sync.

```python
# flashcard.py - Business logic mixed with routing
@flashcard_bp.route('/start/<tab_name>', methods=['POST'])
def start_learning(tab_name: str):
    # Get user's spreadsheet (should be in service)
    user_spreadsheet_id = get_user_spreadsheet_id(session)

    # Read cards from Google Sheets (should be in service)
    card_set = read_card_set(worksheet_name=tab_name, spreadsheet_id=user_spreadsheet_id)
    cards = card_set.get_cards_to_review(limit=config.MAX_CARDS_PER_SESSION)

    # Store in session (should be in service)
    cards_data = []
    for card in cards:
        card_dict = card.model_dump()
        # ... complex serialization logic

    sm.set(sk.LEARNING_CARDS, cards_data)
    # ... 30+ more lines of business logic
```

**Why This Is Bad:**
- Routes become 100+ lines long
- Business logic can't be reused
- Hard to test (requires HTTP mocking)
- No API endpoints for client state sync

---

## Phase 1: Session Management Cleanup

**Goal:** All session access through SessionManager, no phantom parameters.

### Step 1.1: Add Missing SessionKeys

Add keys for user spreadsheet and listening mode state.

```python
# app/session_manager.py

class SessionKeys(Enum):
    # ... existing keys ...

    # User namespace - Add spreadsheet caching
    USER_ID = 'user.id'
    USER_GOOGLE_ID = 'user.google_id'
    USER_SPREADSHEET_ID = 'user.spreadsheet_id'  # ← NEW: Cache active spreadsheet

    # Listening namespace - NEW: Support listening mode state
    LISTENING_TAB_NAME = 'listening.tab_name'
    LISTENING_SHEET_GID = 'listening.sheet_gid'
    LISTENING_CURRENT_INDEX = 'listening.current_index'
    LISTENING_TOTAL_COUNT = 'listening.total_count'
    LISTENING_IS_PLAYING = 'listening.is_playing'
    LISTENING_IS_PAUSED = 'listening.is_paused'
    LISTENING_LOOP_COUNT = 'listening.loop_count'
```

**Why:** Enables listening mode state persistence and eliminates repeated DB queries for spreadsheet ID.

---

### Step 1.2: Remove Phantom Parameters

Update function signatures to remove unused `session_obj` parameters.

**File:** `src/user_manager.py`

```python
# ❌ BEFORE: Misleading parameter
def get_user_spreadsheet_id(session_obj):
    """Get the user's active spreadsheet ID from database"""
    user = get_current_user()
    if not user:
        return None
    active_spreadsheet = get_user_active_spreadsheet(user.id)
    return active_spreadsheet.spreadsheet_id if active_spreadsheet else None

# ✅ AFTER: Clean signature
def get_user_spreadsheet_id() -> str | None:
    """
    Get the user's active spreadsheet ID.

    First checks session cache, then queries database if needed.

    Session Access:
        - Reads: USER_ID (via get_current_user)
        - Reads: USER_SPREADSHEET_ID (cache)
        - Writes: USER_SPREADSHEET_ID (cache)

    Returns:
        Active spreadsheet ID or None if not found
    """
    # Try cache first
    cached_id = sm.get(sk.USER_SPREADSHEET_ID)
    if cached_id:
        return cached_id

    # Cache miss - query database
    user = get_current_user()
    if not user:
        return None

    active_spreadsheet = get_user_active_spreadsheet(user.id)
    if active_spreadsheet:
        # Cache the result
        sm.set(sk.USER_SPREADSHEET_ID, active_spreadsheet.spreadsheet_id)
        return active_spreadsheet.spreadsheet_id

    return None
```

**Functions to Update:**

1. `get_user_spreadsheet_id(session_obj)` → `get_user_spreadsheet_id()`
2. `set_user_spreadsheet(session_obj, ...)` → `set_user_spreadsheet(...)`
3. `clear_user_session(session_obj)` → `clear_user_session()`
4. `login_user(session_obj, ...)` → `login_user(...)`
5. `get_current_user_from_session(session_obj)` → `get_current_user_from_session()`

**Note:** Add docstring section documenting session access patterns!

---

### Step 1.3: Update All Call Sites

Update imports and function calls across route files.

```python
# ❌ BEFORE (flashcard.py)
from flask import Blueprint, redirect, render_template, request, session, url_for
# ...
user_spreadsheet_id = get_user_spreadsheet_id(session)

# ✅ AFTER
from flask import Blueprint, redirect, render_template, request, url_for  # No session import
# ...
user_spreadsheet_id = get_user_spreadsheet_id()  # No parameter
```

**Files to Update:**
- `src/routes/flashcard.py` (~8 call sites)
- `src/routes/settings.py` (~3 call sites)
- `src/routes/auth.py` (~2 call sites)

**Validation:**
```bash
# Verify no direct session imports remain (except in session_manager.py)
grep -r "from flask import.*session" app/routes/

# Should only find session imports that are legitimate (like request handling)
```

---

### Step 1.4: Add Cache Invalidation

When user changes spreadsheet, clear cache.

```python
# app/user_manager.py

def set_user_spreadsheet(spreadsheet_id: str, spreadsheet_url: str | None = None,
                        spreadsheet_name: str | None = None):
    """Set a spreadsheet as active for the current user"""
    user = get_current_user()
    if not user:
        raise Exception('User not logged in')

    # Add/update spreadsheet in database
    user_spreadsheet = add_user_spreadsheet(
        user_id=user.id,
        spreadsheet_id=spreadsheet_id,
        spreadsheet_url=spreadsheet_url,
        spreadsheet_name=spreadsheet_name,
        make_active=True,
    )

    # ✅ NEW: Update session cache
    sm.set(sk.USER_SPREADSHEET_ID, spreadsheet_id)

    # Clear learning state (cards might be from old spreadsheet)
    sm.clear_namespace('learning')

    logger.info(f'Set active spreadsheet {spreadsheet_id} for user {user.email}')
    return user_spreadsheet

def clear_user_session():
    """Clear user authentication data from session"""
    sm.clear_namespace('auth')
    sm.clear_namespace('user')
    sm.clear_namespace('learning')
    sm.clear_namespace('listening')  # ✅ NEW: Clear listening state
    sm.clear_namespace('review')

    logger.info('User session cleared')
```

---

### Phase 1 Checklist

- [ ] Add `USER_SPREADSHEET_ID` to SessionKeys
- [ ] Add `LISTENING_*` keys to SessionKeys
- [ ] Update `get_user_spreadsheet_id()` - remove parameter, add caching
- [ ] Update `set_user_spreadsheet()` - remove parameter, add cache update
- [ ] Update `clear_user_session()` - remove parameter, clear listening namespace
- [ ] Update `login_user()` - remove parameter
- [ ] Update `get_current_user_from_session()` - remove parameter
- [ ] Update all call sites in `flashcard.py`
- [ ] Update all call sites in `settings.py`
- [ ] Update all call sites in `auth.py`
- [ ] Remove unused `session` imports
- [ ] Run tests
- [ ] Manual QA - verify login, spreadsheet selection, learning sessions

**Estimated Time:** 2-3 hours

---

## Phase 2: State API Layer

**Goal:** Create API endpoints for client-server state synchronization.

### Step 2.1: Create State API Blueprint

New file: `src/routes/state_api.py`

```python
"""
State management API for client-server synchronization.

Provides endpoints for managing session state that needs to be
accessible from JavaScript (listening mode, progress tracking, etc.)
"""

from flask import Blueprint, jsonify, request
from app.session_manager import SessionKeys as sk, SessionManager as sm
from app.user_manager import is_authenticated
from app.models import ListeningState, LearningProgress
import logging

logger = logging.getLogger(__name__)

# Create blueprint
state_api_bp = Blueprint('state_api', __name__, url_prefix='/api/state')


# ==================== Listening Mode State ====================

@state_api_bp.route('/listening', methods=['GET'])
def get_listening_state():
    """
    Get current listening mode state.

    Returns:
        JSON with listening session state or null if no active session
    """
    if not is_authenticated():
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    # Check if listening session exists
    if not sm.has(sk.LISTENING_TAB_NAME):
        return jsonify({'success': True, 'state': None})

    state = {
        'tab_name': sm.get(sk.LISTENING_TAB_NAME),
        'sheet_gid': sm.get(sk.LISTENING_SHEET_GID),
        'current_index': sm.get(sk.LISTENING_CURRENT_INDEX, 0),
        'total_count': sm.get(sk.LISTENING_TOTAL_COUNT, 0),
        'is_playing': sm.get(sk.LISTENING_IS_PLAYING, False),
        'is_paused': sm.get(sk.LISTENING_IS_PAUSED, False),
        'loop_count': sm.get(sk.LISTENING_LOOP_COUNT, 1),
    }

    return jsonify({'success': True, 'state': state})


@state_api_bp.route('/listening', methods=['POST'])
def update_listening_state():
    """
    Update listening mode state.

    Body:
        {
            "tab_name": "Common Words",
            "sheet_gid": 12345,
            "current_index": 5,
            "total_count": 50,
            "is_playing": true,
            "is_paused": false,
            "loop_count": 1
        }
    """
    if not is_authenticated():
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    try:
        data = request.get_json()

        # Validate with Pydantic (defined in Phase 2.2)
        state = ListeningState(**data)

        # Store in session
        sm.set(sk.LISTENING_TAB_NAME, state.tab_name)
        sm.set(sk.LISTENING_SHEET_GID, state.sheet_gid)
        sm.set(sk.LISTENING_CURRENT_INDEX, state.current_index)
        sm.set(sk.LISTENING_TOTAL_COUNT, state.total_count)
        sm.set(sk.LISTENING_IS_PLAYING, state.is_playing)
        sm.set(sk.LISTENING_IS_PAUSED, state.is_paused)
        sm.set(sk.LISTENING_LOOP_COUNT, state.loop_count)

        logger.info(f'Listening state updated: {state.tab_name}, card {state.current_index}/{state.total_count}')

        return jsonify({'success': True, 'message': 'State updated'})

    except Exception as e:
        logger.error(f'Error updating listening state: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 400


@state_api_bp.route('/listening', methods=['DELETE'])
def clear_listening_state():
    """Clear listening mode state (session ended)"""
    if not is_authenticated():
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    sm.clear_namespace('listening')
    logger.info('Listening state cleared')

    return jsonify({'success': True, 'message': 'State cleared'})


# ==================== Learning Progress ====================

@state_api_bp.route('/learning/progress', methods=['GET'])
def get_learning_progress():
    """
    Get current learning session progress.

    Returns:
        {
            "active_tab": "Common Words",
            "current_index": 5,
            "total_cards": 20,
            "answers_count": 5,
            "reviewing": false
        }
    """
    if not is_authenticated():
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    if not sm.has(sk.LEARNING_ACTIVE_TAB):
        return jsonify({'success': True, 'progress': None})

    progress = {
        'active_tab': sm.get(sk.LEARNING_ACTIVE_TAB),
        'current_index': sm.get(sk.LEARNING_CURRENT_INDEX, 0),
        'total_cards': len(sm.get(sk.LEARNING_CARDS, [])),
        'answers_count': len(sm.get(sk.LEARNING_ANSWERS, [])),
        'reviewing': sm.get(sk.LEARNING_REVIEWING_INCORRECT, False),
    }

    return jsonify({'success': True, 'progress': progress})


# ==================== Bulk State Sync ====================

@state_api_bp.route('/sync', methods=['POST'])
def sync_state():
    """
    Bulk state synchronization.

    Client sends its state, server responds with canonical state.
    Used for resolving conflicts or recovering from errors.

    Body:
        {
            "client_state": {
                "listening": {...},
                "learning_progress": {...}
            }
        }

    Returns:
        {
            "server_state": {
                "listening": {...},
                "learning_progress": {...}
            },
            "conflicts": []
        }
    """
    if not is_authenticated():
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    # TODO: Implement conflict resolution logic
    # For Phase 2, just return server state as canonical

    server_state = {
        'listening': get_listening_state().get_json().get('state'),
        'learning_progress': get_learning_progress().get_json().get('progress'),
    }

    return jsonify({
        'success': True,
        'server_state': server_state,
        'conflicts': []
    })
```

---

### Step 2.2: Add State Validation Models

Update `src/models.py` with Pydantic models for state validation.

```python
# app/models.py

from pydantic import BaseModel, Field, field_validator
from typing import Optional

# ... existing models ...

class ListeningState(BaseModel):
    """Listening mode session state"""
    tab_name: str = Field(..., min_length=1, max_length=200)
    sheet_gid: int | None = None
    current_index: int = Field(default=0, ge=0)
    total_count: int = Field(default=0, ge=0)
    is_playing: bool = False
    is_paused: bool = False
    loop_count: int = Field(default=1, ge=1)

    @field_validator('current_index')
    @classmethod
    def validate_index(cls, v, info):
        """Current index should not exceed total count"""
        total = info.data.get('total_count', 0)
        if v > total:
            raise ValueError(f'current_index ({v}) cannot exceed total_count ({total})')
        return v


class LearningProgress(BaseModel):
    """Learning session progress snapshot"""
    active_tab: str
    current_index: int = Field(ge=0)
    total_cards: int = Field(ge=0)
    answers_count: int = Field(ge=0)
    reviewing: bool = False


class StateUpdateRequest(BaseModel):
    """Request body for state updates"""
    listening: Optional[ListeningState] = None
    learning_progress: Optional[LearningProgress] = None


class StateSyncResponse(BaseModel):
    """Response for bulk state sync"""
    success: bool
    server_state: dict
    conflicts: list[str] = []
```

---

### Step 2.3: Register State API Blueprint

Update `src/routes/__init__.py`:

```python
# app/routes/__init__.py

from flask import Flask
from .auth import auth_bp
from .flashcard import flashcard_bp
from .settings import settings_bp
from .api import api_bp
from .admin import admin_bp
from .test import test_bp
from .state_api import state_api_bp  # ✅ NEW


def register_blueprints(app: Flask) -> None:
    """Register all blueprints with the Flask app."""
    app.register_blueprint(auth_bp)
    app.register_blueprint(flashcard_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(test_bp)
    app.register_blueprint(state_api_bp)  # ✅ NEW
```

---

### Phase 2 Checklist

- [ ] Create `src/routes/state_api.py` with blueprint
- [ ] Implement `GET /api/state/listening` endpoint
- [ ] Implement `POST /api/state/listening` endpoint
- [ ] Implement `DELETE /api/state/listening` endpoint
- [ ] Implement `GET /api/state/learning/progress` endpoint
- [ ] Implement `POST /api/state/sync` endpoint (basic version)
- [ ] Add `ListeningState` model to `models.py`
- [ ] Add `LearningProgress` model to `models.py`
- [ ] Add `StateUpdateRequest` model to `models.py`
- [ ] Register `state_api_bp` in `routes/__init__.py`
- [ ] Add API tests (see Testing Strategy section)
- [ ] Document API endpoints in Swagger/OpenAPI (optional)

**Estimated Time:** 4-5 hours

---

## Phase 3: Service Layer Extraction

**Goal:** Extract business logic from routes into reusable services.

### Step 3.1: Create Service Structure

```
src/
├── services/
│   ├── __init__.py
│   ├── learning_service.py      # Learning session management
│   ├── listening_service.py     # Listening mode management
│   ├── spreadsheet_service.py   # Google Sheets operations
│   └── user_service.py          # User operations
```

---

### Step 3.2: Learning Service

New file: `src/services/learning_service.py`

```python
"""
Learning session service - manages flashcard learning sessions.

Handles business logic for:
- Starting/ending learning sessions
- Card progression and review
- Answer processing and statistics
- Batch updates to spreadsheet
"""

from typing import List
import logging

from app.models import Card, CardSet
from app.session_manager import SessionKeys as sk, SessionManager as sm
from app.gsheet import read_card_set, update_spreadsheet
from app.config import config
from app.utils import format_timestamp, get_timestamp, parse_timestamp

logger = logging.getLogger(__name__)


class LearningService:
    """Service for managing learning sessions"""

    @staticmethod
    def start_session(tab_name: str, spreadsheet_id: str) -> dict:
        """
        Start a new learning session.

        Args:
            tab_name: Worksheet name to learn from
            spreadsheet_id: Google Sheets spreadsheet ID

        Returns:
            dict with session info (card_count, tab_name, etc.)

        Raises:
            ValueError: If tab not found or no cards available
        """
        try:
            # Read cards from the specified tab
            card_set = read_card_set(
                worksheet_name=tab_name,
                spreadsheet_id=spreadsheet_id
            )

            # Get cards to review
            cards = card_set.get_cards_to_review(
                limit=config.MAX_CARDS_PER_SESSION,
                ignore_unshown=False
            )

            if not cards:
                raise ValueError(f'No cards available in tab "{tab_name}"')

            logger.info(f'Starting session: {len(cards)} cards from "{tab_name}"')

            # Convert cards to session format
            cards_data = []
            for card in cards:
                card_dict = card.model_dump()
                card_dict['last_shown'] = format_timestamp(card.last_shown)
                cards_data.append(card_dict)

            # Initialize session state
            sm.set(sk.LEARNING_CARDS, cards_data)
            sm.set(sk.LEARNING_CURRENT_INDEX, 0)
            sm.set(sk.LEARNING_ANSWERS, [])
            sm.set(sk.LEARNING_INCORRECT_CARDS, [])
            sm.set(sk.LEARNING_REVIEWING_INCORRECT, False)
            sm.set(sk.LEARNING_ACTIVE_TAB, tab_name)
            sm.set(sk.LEARNING_ORIGINAL_COUNT, len(cards))
            sm.set(sk.LEARNING_SHEET_GID, card_set.gid)

            return {
                'card_count': len(cards),
                'tab_name': tab_name,
                'sheet_gid': card_set.gid,
            }

        except Exception as e:
            logger.error(f'Error starting session for "{tab_name}": {e}', exc_info=True)
            raise

    @staticmethod
    def process_answer(user_answer: str) -> dict:
        """
        Process user's answer to current card.

        Args:
            user_answer: User's input answer

        Returns:
            dict with result (is_correct, level_change, etc.)
        """
        # Get current card
        cards = sm.get(sk.LEARNING_CARDS, [])
        index = sm.get(sk.LEARNING_CURRENT_INDEX, 0)
        reviewing = sm.get(sk.LEARNING_REVIEWING_INCORRECT, False)

        if reviewing:
            original_index = sm.get(sk.LEARNING_INCORRECT_CARDS)[index]
            current_card = cards[original_index]
        else:
            current_card = cards[index]

        # Check answer
        correct_answers = [current_card['word'].strip().lower()]
        is_correct = user_answer.strip().lower() in correct_answers

        # Update card statistics
        card = Card(**current_card)
        original_level = card.level.value

        card.cnt_shown += 1
        card.last_shown = get_timestamp()

        if is_correct:
            card.cnt_corr_answers += 1
            card.level = card.level.next_level()
        else:
            card.level = card.level.previous_level()

        # Store answer
        answers = sm.get(sk.LEARNING_ANSWERS, [])
        answer_data = {
            'card_index': original_index if reviewing else index,
            'word': current_card['word'],
            'translation': current_card['translation'],
            'user_answer': user_answer,
            'correct_answer': current_card['word'],
            'is_correct': is_correct,
            'timestamp': get_timestamp().isoformat(),
            'is_review': reviewing,
        }
        answers.append(answer_data)
        sm.set(sk.LEARNING_ANSWERS, answers)

        # Track incorrect cards
        if not is_correct and not reviewing:
            incorrect_cards = sm.get(sk.LEARNING_INCORRECT_CARDS, [])
            incorrect_cards.append(index)
            sm.set(sk.LEARNING_INCORRECT_CARDS, incorrect_cards)

        # Update session with modified card
        card_dict = card.model_dump()
        card_dict['last_shown'] = format_timestamp(card.last_shown)

        if reviewing:
            cards[original_index] = card_dict
        else:
            cards[index] = card_dict
        sm.set(sk.LEARNING_CARDS, cards)

        level_change = {
            'from': original_level,
            'to': card.level.value,
            'is_correct': is_correct,
        }
        sm.set(sk.LEARNING_LAST_LEVEL_CHANGE, level_change)

        logger.info(f'Answer processed: {"✅" if is_correct else "❌"} Level {original_level}→{card.level.value}')

        return {
            'is_correct': is_correct,
            'level_change': level_change,
            'card_index': index,
        }

    @staticmethod
    def batch_update_cards(spreadsheet_id: str) -> bool:
        """
        Batch update all modified cards to Google Sheets.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID

        Returns:
            True if successful, False otherwise
        """
        try:
            cards_data = sm.get(sk.LEARNING_CARDS, [])
            active_tab = sm.get(sk.LEARNING_ACTIVE_TAB)

            if not cards_data or not active_tab:
                logger.warning('No cards or tab to update')
                return False

            # Convert to Card objects
            cards_to_update = []
            for card_data in cards_data:
                if card_data.get('last_shown'):
                    card_data['last_shown'] = parse_timestamp(card_data['last_shown'])
                cards_to_update.append(Card(**card_data))

            logger.info(f'Batch updating {len(cards_to_update)} cards to {active_tab}')
            update_spreadsheet(active_tab, cards_to_update, spreadsheet_id=spreadsheet_id)
            logger.info('✅ Batch update completed')

            return True

        except Exception as e:
            logger.error(f'Batch update failed: {e}', exc_info=True)
            return False

    @staticmethod
    def get_session_results() -> dict:
        """
        Get results for completed session.

        Returns:
            dict with statistics (total, correct, percentage, etc.)
        """
        answers = sm.get(sk.LEARNING_ANSWERS, [])
        original_count = sm.get(sk.LEARNING_ORIGINAL_COUNT, len(answers))
        incorrect_cards = sm.get(sk.LEARNING_INCORRECT_CARDS, [])

        total_answered = len(answers)
        correct_answers = sum(1 for a in answers if a['is_correct'])
        review_count = len([a for a in answers if a.get('card_index', 0) in incorrect_cards])
        first_attempt_count = total_answered - review_count
        accuracy = (correct_answers / total_answered * 100) if total_answered > 0 else 0

        return {
            'total': total_answered,
            'correct': correct_answers,
            'percentage': int(accuracy),
            'review_count': review_count,
            'first_attempt_count': first_attempt_count,
            'original_count': original_count,
            'answers': answers,
        }

    @staticmethod
    def clear_session():
        """Clear learning session state"""
        sm.clear_namespace('learning')
        logger.info('Learning session cleared')
```

---

### Step 3.3: Refactor Routes to Use Services

Update `src/routes/flashcard.py`:

```python
# flashcard.py - BEFORE refactoring (100+ lines of business logic)

@flashcard_bp.route('/start/<tab_name>', methods=['POST'])
def start_learning(tab_name: str):
    # ... 80 lines of business logic ...
    return redirect(url_for('flashcard.show_card'))


# flashcard.py - AFTER refactoring (clean routing)

from app.services.learning_service import LearningService


@flashcard_bp.route('/start/<tab_name>', methods=['POST'])
def start_learning(tab_name: str):
    """Start a learning session with cards from the specified tab."""
    logger.info(f'Starting learning session: {tab_name}')

    try:
        # Get user's spreadsheet
        user_spreadsheet_id = get_user_spreadsheet_id()

        # Delegate to service
        session_info = LearningService.start_session(tab_name, user_spreadsheet_id)

        logger.info(f'Session started: {session_info["card_count"]} cards')
        return redirect(url_for('flashcard.show_card'))

    except ValueError as e:
        logger.error(f'Invalid session: {e}')
        flash(str(e), 'error')
        return redirect(url_for('flashcard.index'))

    except Exception as e:
        logger.error(f'Error starting session: {e}', exc_info=True)
        flash('Failed to start learning session', 'error')
        return redirect(url_for('flashcard.index'))


@flashcard_bp.route('/answer', methods=['POST'])
def process_answer():
    """Process user's answer to a flashcard."""
    user_answer = request.form.get('user_answer', '').strip()

    try:
        result = LearningService.process_answer(user_answer)
        is_correct = result['is_correct']

        feedback_url = url_for(
            'flashcard.show_feedback',
            correct='yes' if is_correct else 'no'
        )
        return redirect(feedback_url)

    except Exception as e:
        logger.error(f'Error processing answer: {e}', exc_info=True)
        flash('Error processing answer', 'error')
        return redirect(url_for('flashcard.show_card'))
```

**Benefits:**
- Routes now 10-20 lines instead of 100+
- Business logic testable without HTTP mocking
- Logic reusable from other routes or CLI tools
- Clear separation of concerns

---

### Phase 3 Checklist

- [ ] Create `src/services/` directory
- [ ] Create `learning_service.py` with LearningService class
- [ ] Migrate `start_learning` logic to service
- [ ] Migrate `process_answer` logic to service
- [ ] Migrate `batch_update_cards` logic to service
- [ ] Create `listening_service.py` (similar pattern)
- [ ] Create `user_service.py` (consolidate user operations)
- [ ] Refactor `flashcard.py` routes to use services
- [ ] Refactor other route files as needed
- [ ] Add service-level tests
- [ ] Update documentation

**Estimated Time:** 6-8 hours

---

## Phase 4: Database Optimization

**Goal:** Review and optimize database usage patterns.

### Step 4.1: Analyze Current Usage

Current schema:

```python
# database.py
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_user_id = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserSpreadsheet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    spreadsheet_id = db.Column(db.String(255))
    spreadsheet_url = db.Column(db.String(512))
    spreadsheet_name = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=False)
```

**Current Pattern:**
- User info stored in DB
- Spreadsheet associations stored in DB
- Card data stored in Google Sheets
- Session state stored in Flask session

**Questions to Answer:**
1. Should we cache card data in DB for faster access?
2. Should learning progress be persisted to DB?
3. Should we add indexes for common queries?

---

### Step 4.2: Potential Optimizations

**Option A: Add Learning Progress Table** (for analytics)

```python
class LearningSession(db.Model):
    """Track learning sessions for analytics"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    spreadsheet_id = db.Column(db.String(255))
    tab_name = db.Column(db.String(255))
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    cards_studied = db.Column(db.Integer)
    cards_correct = db.Column(db.Integer)
    accuracy_percentage = db.Column(db.Float)
```

**Benefits:**
- Track user progress over time
- Generate learning statistics
- Identify problem areas

**Drawbacks:**
- Additional DB writes
- Need migration

**Option B: Cache Card Metadata** (for performance)

```python
class CardCache(db.Model):
    """Cache card metadata for faster loading"""
    id = db.Column(db.Integer, primary_key=True)
    spreadsheet_id = db.Column(db.String(255))
    sheet_gid = db.Column(db.Integer)
    row_number = db.Column(db.Integer)
    word = db.Column(db.String(255))
    translation = db.Column(db.String(512))
    level = db.Column(db.Integer)
    last_shown = db.Column(db.DateTime)
    cached_at = db.Column(db.DateTime, default=datetime.utcnow)
```

**Benefits:**
- Faster card loading (no API call)
- Works offline (to a degree)
- Reduces API quota usage

**Drawbacks:**
- Sync complexity (DB vs Sheets)
- Stale data issues
- Duplicate data storage

**Recommendation:** Start with Option A (analytics), skip Option B unless performance becomes an issue.

---

### Phase 4 Checklist

- [ ] Add `LearningSession` model for analytics (optional)
- [ ] Add indexes for common queries (`user_id`, `spreadsheet_id`)
- [ ] Create migration script if adding tables
- [ ] Update services to record session completion
- [ ] Add analytics endpoints (optional)
- [ ] Document DB schema in ERD diagram

**Estimated Time:** 2-3 hours

---

## Testing Strategy

### Unit Tests

**Test Session Manager:**

```python
# tests/test_session_manager.py
from app.session_manager import SessionManager as sm, SessionKeys as sk


def test_get_set_session():
    """Test basic get/set operations"""
    sm.set(sk.USER_ID, 123)
    assert sm.get(sk.USER_ID) == 123


def test_clear_namespace():
    """Test namespace clearing"""
    sm.set(sk.LEARNING_CARDS, [])
    sm.set(sk.LEARNING_CURRENT_INDEX, 0)
    sm.clear_namespace('learning')
    assert not sm.has(sk.LEARNING_CARDS)
    assert not sm.has(sk.LEARNING_CURRENT_INDEX)
```

**Test Services:**

```python
# tests/test_learning_service.py
from app.services.learning_service import LearningService


def test_start_session(mock_spreadsheet):
    """Test learning session initialization"""
    result = LearningService.start_session('Common Words', 'sheet_123')
    assert result['card_count'] > 0
    assert result['tab_name'] == 'Common Words'


def test_process_answer():
    """Test answer processing logic"""
    # Setup session first
    result = LearningService.process_answer('olá')
    assert 'is_correct' in result
    assert 'level_change' in result
```

---

### Integration Tests

```python
# tests/test_state_api.py
def test_listening_state_crud(client, auth_headers):
    """Test listening state create/read/update/delete"""

    # Create state
    state = {
        'tab_name': 'Test Tab',
        'current_index': 5,
        'total_count': 50,
        'is_playing': True
    }
    response = client.post('/api/state/listening', json=state, headers=auth_headers)
    assert response.status_code == 200

    # Read state
    response = client.get('/api/state/listening', headers=auth_headers)
    data = response.get_json()
    assert data['state']['current_index'] == 5

    # Delete state
    response = client.delete('/api/state/listening', headers=auth_headers)
    assert response.status_code == 200
```

---

## Migration Guide

### Incremental Migration Strategy

**Week 1: Phase 1 (Session Cleanup)**
- Day 1-2: Add SessionKeys, update function signatures
- Day 3: Update call sites in flashcard.py
- Day 4: Update call sites in other route files
- Day 5: Testing and bug fixes

**Week 2: Phase 2 (State API)**
- Day 1-2: Create state_api.py blueprint
- Day 3: Add Pydantic models
- Day 4-5: Testing and integration

**Week 3: Phase 3 (Service Layer)**
- Day 1-3: Extract LearningService
- Day 4: Extract other services
- Day 5: Refactor routes, testing

**Week 4: Phase 4 + Polish**
- Day 1-2: Database review and optimizations
- Day 3-5: Documentation, testing, deployment

---

## Rollback Strategy

**If Issues Arise:**

1. **Phase 1 Issues:**
   - Revert function signatures
   - Add back session parameters temporarily
   - Fix issues, then retry

2. **Phase 2 Issues:**
   - Unregister state API blueprint
   - Client code degrades gracefully (no state persistence)
   - Fix issues, redeploy

3. **Phase 3 Issues:**
   - Services are additive - can keep both old and new code
   - Gradually migrate routes one at a time
   - Easy rollback per-route

**Feature Flags (Optional):**

```python
# config.py
USE_SERVICE_LAYER = env.bool('USE_SERVICE_LAYER', default=False)

# routes/flashcard.py
if config.USE_SERVICE_LAYER:
    result = LearningService.start_session(tab_name, spreadsheet_id)
else:
    # Old inline logic
    pass
```

---

## Success Metrics

**Code Quality:**
- [ ] All session access through SessionManager
- [ ] No phantom parameters
- [ ] Route files < 200 lines each
- [ ] Business logic in services, not routes
- [ ] 80%+ test coverage

**Performance:**
- [ ] No regression in page load times
- [ ] API endpoints < 200ms response time
- [ ] Listening state survives page reload

**User Experience:**
- [ ] Can resume listening sessions
- [ ] No ghost audio after navigation
- [ ] Learning progress persists correctly

---

## Next Steps

1. Review this document
2. Create feature branch: `feat/backend-cleanup-phase1`
3. Start with Phase 1, commit frequently
4. Create PR for review after each phase
5. Document learnings and edge cases

---

## Questions / Discussion

**Before Starting:**
- Should we add analytics (LearningSession model)?
- Do we need conflict resolution for state sync?
- Should we implement feature flags for gradual rollout?
- What's our testing environment strategy?

**Add your notes here as you implement:**
- [ ] Phase 1 notes:
- [ ] Phase 2 notes:
- [ ] Phase 3 notes:
- [ ] Phase 4 notes:
