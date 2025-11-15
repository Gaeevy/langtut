# Frontend State Management Architecture

**Version:** 1.0
**Last Updated:** 2024
**Status:** Planning Document

---

## Table of Contents

1. [Overview](#overview)
2. [Current State Problems](#current-state-problems)
3. [Hybrid State Model](#hybrid-state-model)
4. [Implementation Plan](#implementation-plan)
5. [JavaScript Module Organization](#javascript-module-organization)
6. [State Synchronization Patterns](#state-synchronization-patterns)
7. [Error Handling & Recovery](#error-handling--recovery)
8. [Testing Strategy](#testing-strategy)

---

## Overview

### Current Architecture

```
┌─────────────┐
│   Browser   │
├─────────────┤
│ listening.js│ ← 1000+ lines, all in-memory state
│   tts.js    │ ← sessionStorage for cache only
│             │
│ Window obj  │ ← Global state, lost on navigation
└─────────────┘
       ↕ API calls (only for data fetch)
┌─────────────┐
│   Flask     │
├─────────────┤
│ Session     │ ← Learning state only
│  Database   │ ← User/Spreadsheet only
└─────────────┘
```

**Problems:**
- Listening state lost on page reload
- No sync between client/server
- Race conditions with async operations
- Ghost audio after navigation

---

### Target Architecture (Hybrid Model)

```
┌──────────────────────────────────┐
│          Browser                  │
├──────────────────────────────────┤
│  ┌────────────────────────────┐  │
│  │  StateManager (Central)    │  │ ← NEW: Central state management
│  └────────────────────────────┘  │
│         ↕                ↕        │
│  ┌──────────┐    ┌──────────┐   │
│  │ UI State │    │ API State│   │
│  │(ephemeral)    │(persisted)   │
│  └──────────┘    └──────────┘   │
│                                   │
│  localStorage: TTS cache          │ ← Long-term cache
│  sessionStorage: UI preferences   │ ← Session-only data
└──────────────────────────────────┘
       ↕ State Sync API
┌──────────────────────────────────┐
│          Flask                    │
├──────────────────────────────────┤
│  Session: Canonical state         │ ← Single source of truth
│  Database: Persistent data        │
└──────────────────────────────────┘
```

**Benefits:**
- Listening state survives reload ✅
- Resume sessions after navigation ✅
- No race conditions ✅
- Clean audio cleanup ✅
- Testable state management ✅

---

## Current State Problems

### Problem 1: State Lives Only in Memory

```javascript
// listening.js - ListeningManager constructor
class ListeningManager {
    constructor() {
        this.currentSession = null;      // Lost on reload!
        this.isPlaying = false;          // Lost on reload!
        this.currentCardIndex = 0;       // Lost on reload!
        this.cards = [];                 // Lost on reload!
        this.tabName = '';               // Lost on reload!
    }
}
```

**User Impact:**
1. User opens listening modal for "Common Words" (50 cards)
2. Gets to card 20
3. Browser refreshes or navigates away
4. Returns to page → Listening state completely lost
5. Must restart from card 1 ❌

---

### Problem 2: No Synchronization with Server

```javascript
// Current: Client fetches data, server knows nothing about playback
async startListening(tabName) {
    const response = await fetch(`/api/cards/${tabName}`);
    this.cards = response.cards;  // Client has cards
    this.isPlaying = true;        // Server has no idea!
}
```

**Issues:**
- Server can't help recover lost state
- Can't sync across devices/tabs
- No way to resume interrupted sessions
- Analytics incomplete (server doesn't see listening activity)

---

### Problem 3: Race Conditions

```javascript
// listening.js - Multiple async operations without proper cleanup
async playNextCard() {
    const card = this.cards[this.currentCardIndex];

    // Start playing card 1
    await this.playCardAudio(card);  // Takes 3 seconds

    // User closes modal while this is running!
    // Promise continues executing in background ❌

    this.currentCardIndex++;
    await this.playNextCard();  // Ghost operation!
}
```

**Current Mitigation:** `operationToken` pattern (complex, brittle)

```javascript
// Complex token validation everywhere
if (operationToken !== this.currentOperationToken) {
    console.log('Token expired, aborting');
    return;
}
```

**Better Solution:** State machine + proper cleanup

---

### Problem 4: Scattered State Access

```javascript
// State accessed in multiple ways across files

// listening.js
this.currentCardIndex = 5;

// tts.js
window.ttsManager.audioCache.set(key, value);

// card.html (inline script)
window.cardData = {{ card|tojson }};

// No single source of truth!
```

---

## Hybrid State Model

### State Classification

**Tier 1: Server-Authoritative (Session State)**
- Stored in Flask session
- Synchronized to client on page load
- Client updates via API calls
- Survives page reload

**Examples:**
- Learning session (cards, progress, answers)
- Listening session (tab, index, playing status)
- User preferences
- Active spreadsheet ID

**Tier 2: Client-Authoritative (UI State)**
- Stored in JavaScript only
- Ephemeral (resets on page load)
- Does not need persistence

**Examples:**
- Modal open/closed state
- Animations in progress
- Hover states
- Temporary UI feedback

**Tier 3: Client-Cached (Performance Data)**
- Stored in localStorage/sessionStorage
- Generated client-side
- Can be regenerated if lost

**Examples:**
- TTS audio cache
- UI preferences (theme, layout)
- Recently used spreadsheets

---

### State Ownership Rules

| State Type | Owner | Storage | Sync Method |
|------------|-------|---------|-------------|
| Learning cards | Server | Flask session | Page render + API |
| Listening progress | Server | Flask session | API polling |
| TTS cache | Client | localStorage | None |
| Audio playing | Client | Memory | None (ephemeral) |
| Modal visible | Client | Memory | None (ephemeral) |
| User spreadsheet | Server | Database + Session | On login |

---

## Implementation Plan

### Phase 1: Create StateManager (Foundation)

New file: `static/js/state-manager.js`

```javascript
/**
 * Centralized state management for client-side application state.
 *
 * Provides:
 * - Single source of truth for application state
 * - Automatic sync with server
 * - State persistence across page reloads
 * - Event-based state updates
 */

class StateManager {
    constructor() {
        // In-memory state cache
        this.state = {
            listening: null,
            learning: null,
            user: null,
        };

        // Event listeners for state changes
        this.listeners = new Map();

        // Sync status
        this.isSyncing = false;
        this.lastSyncTime = null;

        // Initialize from server on page load
        this.initializeFromServer();
    }

    /**
     * Initialize state from server on page load
     */
    async initializeFromServer() {
        try {
            // Fetch all state from server
            const response = await fetch('/api/state/all');
            const data = await response.json();

            if (data.success) {
                this.state = data.state;
                this.notifyListeners('*', this.state);
                console.log('✅ State initialized from server:', this.state);
            }
        } catch (error) {
            console.error('❌ Failed to initialize state:', error);
            // Continue with empty state, don't block page load
        }
    }

    /**
     * Get state value
     */
    get(path) {
        // Support dot notation: 'listening.currentIndex'
        return path.split('.').reduce((obj, key) => obj?.[key], this.state);
    }

    /**
     * Set state value (local + sync to server)
     */
    async set(path, value, options = {}) {
        const { syncToServer = true, notify = true } = options;

        // Update local state
        this._setLocal(path, value);

        // Notify listeners if requested
        if (notify) {
            this.notifyListeners(path, value);
        }

        // Sync to server if requested
        if (syncToServer) {
            await this.syncToServer(path, value);
        }
    }

    /**
     * Update local state only (no server sync)
     */
    _setLocal(path, value) {
        const keys = path.split('.');
        const lastKey = keys.pop();
        const target = keys.reduce((obj, key) => {
            if (!obj[key]) obj[key] = {};
            return obj[key];
        }, this.state);

        target[lastKey] = value;
    }

    /**
     * Sync state to server
     */
    async syncToServer(path, value) {
        if (this.isSyncing) {
            console.log('⏳ Sync already in progress, queuing...');
            // TODO: Implement queue
            return;
        }

        this.isSyncing = true;

        try {
            // Determine API endpoint based on path
            const namespace = path.split('.')[0];
            const endpoint = this._getEndpointForNamespace(namespace);

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(value)
            });

            const data = await response.json();

            if (data.success) {
                this.lastSyncTime = Date.now();
                console.log(`✅ State synced to server: ${path}`);
            } else {
                console.error(`❌ Failed to sync state: ${data.error}`);
            }
        } catch (error) {
            console.error('❌ Sync error:', error);
            // TODO: Implement retry logic
        } finally {
            this.isSyncing = false;
        }
    }

    /**
     * Subscribe to state changes
     */
    subscribe(path, callback) {
        if (!this.listeners.has(path)) {
            this.listeners.set(path, []);
        }
        this.listeners.get(path).push(callback);

        // Return unsubscribe function
        return () => {
            const callbacks = this.listeners.get(path);
            const index = callbacks.indexOf(callback);
            if (index > -1) {
                callbacks.splice(index, 1);
            }
        };
    }

    /**
     * Notify listeners of state change
     */
    notifyListeners(path, value) {
        // Notify exact path listeners
        if (this.listeners.has(path)) {
            this.listeners.get(path).forEach(callback => callback(value));
        }

        // Notify wildcard listeners
        if (this.listeners.has('*')) {
            this.listeners.get('*').forEach(callback => callback({ path, value }));
        }
    }

    /**
     * Get API endpoint for namespace
     */
    _getEndpointForNamespace(namespace) {
        const endpoints = {
            listening: '/api/state/listening',
            learning: '/api/state/learning/progress',
        };
        return endpoints[namespace] || '/api/state/sync';
    }

    /**
     * Clear state namespace
     */
    async clear(namespace) {
        this.state[namespace] = null;
        this.notifyListeners(namespace, null);

        // Sync to server
        const endpoint = this._getEndpointForNamespace(namespace);
        await fetch(endpoint, { method: 'DELETE' });
    }

    /**
     * Debug: Log current state
     */
    debug() {
        console.log('🔍 StateManager State:', this.state);
        console.log('🔍 Last Sync:', this.lastSyncTime ? new Date(this.lastSyncTime) : 'Never');
        console.log('🔍 Listeners:', this.listeners.size);
        return this.state;
    }
}

// Global instance
window.stateManager = new StateManager();

// Debug helper
window.debugState = () => window.stateManager.debug();
```

---

### Phase 2: Refactor ListeningManager to Use StateManager

Update `static/js/listening.js`:

```javascript
/**
 * Listening Mode Manager - Refactored to use StateManager
 */

class ListeningManager {
    constructor() {
        // Don't store state locally - use StateManager!
        // Remove: this.currentSession, this.isPlaying, this.cards, etc.

        // Only store truly ephemeral UI state
        this.audioContext = null;
        this.isMobile = this.detectMobile();

        // Subscribe to state changes
        this.setupStateSubscriptions();

        // Initialize UI
        this.initializeUI();
    }

    /**
     * Subscribe to state changes
     */
    setupStateSubscriptions() {
        // Update UI when listening state changes
        window.stateManager.subscribe('listening', (state) => {
            this.onStateChange(state);
        });
    }

    /**
     * Handle state changes from StateManager
     */
    onStateChange(state) {
        if (!state) {
            // State cleared - reset UI
            this.resetUIElements();
            return;
        }

        // Update UI based on new state
        this.updateProgress();

        // Resume playback if needed
        if (state.is_playing && !state.is_paused) {
            this.resumePlayback();
        }
    }

    /**
     * Start listening session
     */
    async startListening(tabName) {
        console.log(`🎵 Starting listening session: ${tabName}`);

        try {
            // Fetch cards from API
            const response = await fetch(`/api/cards/${tabName}`);
            const data = await response.json();

            if (!data.success) {
                throw new Error(data.error);
            }

            // Initialize state via StateManager (auto-syncs to server)
            await window.stateManager.set('listening', {
                tab_name: tabName,
                sheet_gid: data.sheet_gid,
                current_index: 0,
                total_count: data.total_count,
                is_playing: true,
                is_paused: false,
                loop_count: 1,
                cards: data.cards  // Store cards in server session
            });

            console.log('✅ Listening state initialized and synced to server');

            // Start playback
            await this.beginPlayback();

        } catch (error) {
            console.error('❌ Error starting listening:', error);
            this.updateStatus(`Error: ${error.message}`, false);
        }
    }

    /**
     * Play next card (simplified - state managed by StateManager)
     */
    async playNextCard() {
        // Get state from StateManager
        const state = window.stateManager.get('listening');

        if (!state || !state.is_playing || state.is_paused) {
            return;
        }

        // Check if we've reached the end
        if (state.current_index >= state.total_count) {
            await this.restartLoop();
            return;
        }

        const card = state.cards[state.current_index];

        try {
            // Play card audio
            await this.playCardAudio(card);

            // Update index via StateManager (auto-syncs to server)
            await window.stateManager.set(
                'listening.current_index',
                state.current_index + 1
            );

            // Continue to next card
            setTimeout(() => this.playNextCard(), 500);

        } catch (error) {
            console.error('❌ Error playing card:', error);
            // Skip to next card
            await window.stateManager.set(
                'listening.current_index',
                state.current_index + 1
            );
            setTimeout(() => this.playNextCard(), 1000);
        }
    }

    /**
     * Pause playback
     */
    async pausePlayback() {
        // Update state via StateManager
        await window.stateManager.set('listening.is_paused', true);

        // Stop current audio
        if (window.ttsManager?.currentAudio) {
            window.ttsManager.currentAudio.pause();
        }

        // Update UI
        this.updatePauseButton(true);
    }

    /**
     * Resume playback
     */
    async resumePlayback() {
        // Update state via StateManager
        await window.stateManager.set('listening.is_paused', false);

        // Update UI
        this.updatePauseButton(false);

        // Continue playing
        await this.playNextCard();
    }

    /**
     * Stop playback and clear state
     */
    async stopPlayback() {
        console.log('🛑 Stopping playback');

        // Stop all audio
        if (window.ttsManager) {
            window.ttsManager.stopAllAudio();
        }

        // Clear state via StateManager (auto-syncs to server)
        await window.stateManager.clear('listening');

        // Reset UI
        this.resetUIElements();
    }

    /**
     * Update progress UI from current state
     */
    updateProgress() {
        const state = window.stateManager.get('listening');
        if (!state) return;

        const progress = Math.round(((state.current_index + 1) / state.total_count) * 100);

        // Update progress bar
        const progressBar = document.getElementById('listeningProgressBar');
        if (progressBar) {
            progressBar.style.width = `${progress}%`;
        }

        // Update progress text
        const progressText = document.getElementById('progressText');
        if (progressText) {
            progressText.textContent = `${state.current_index + 1} / ${state.total_count} cards`;
        }

        // Update current card display
        if (state.cards && state.cards[state.current_index]) {
            const card = state.cards[state.current_index];
            document.getElementById('currentWord').textContent = card.word;
            document.getElementById('currentExample').textContent = card.example;
        }
    }
}

// Global instance
window.listeningManager = new ListeningManager();
```

**Key Changes:**
- ✅ No more local state storage
- ✅ All state goes through StateManager
- ✅ State automatically syncs to server
- ✅ State survives page reload
- ✅ No more operation tokens (state is canonical)
- ✅ Simpler code (less edge cases)

---

### Phase 3: Add State Recovery on Page Load

Update `static/js/listening.js`:

```javascript
class ListeningManager {
    constructor() {
        // ... existing code ...

        // Check for existing listening session on page load
        this.checkForExistingSession();
    }

    /**
     * Check if there's an existing listening session to resume
     */
    async checkForExistingSession() {
        const state = window.stateManager.get('listening');

        if (!state) {
            console.log('No existing listening session');
            return;
        }

        console.log('🔄 Found existing listening session:', state);

        // Show resume prompt
        this.showResumePrompt(state);
    }

    /**
     * Show prompt to resume interrupted session
     */
    showResumePrompt(state) {
        // Create resume notification
        const notification = document.createElement('div');
        notification.className = 'alert alert-info resume-prompt';
        notification.innerHTML = `
            <strong>Resume Listening Session?</strong>
            <p>You were listening to "${state.tab_name}"
               (Card ${state.current_index + 1} of ${state.total_count})</p>
            <button class="btn btn-primary" id="resumeSessionBtn">
                <i class="fas fa-play"></i> Resume
            </button>
            <button class="btn btn-secondary" id="discardSessionBtn">
                <i class="fas fa-times"></i> Discard
            </button>
        `;

        // Add to page
        const container = document.querySelector('.container');
        if (container) {
            container.insertBefore(notification, container.firstChild);
        }

        // Add event listeners
        document.getElementById('resumeSessionBtn')?.addEventListener('click', async () => {
            notification.remove();
            await this.resumeSession(state);
        });

        document.getElementById('discardSessionBtn')?.addEventListener('click', async () => {
            notification.remove();
            await window.stateManager.clear('listening');
        });
    }

    /**
     * Resume existing session
     */
    async resumeSession(state) {
        console.log('▶️ Resuming listening session');

        // Open listening modal
        const modal = new bootstrap.Modal(document.getElementById('listeningModal'));
        modal.show();

        // Show progress view
        this.showProgressView();

        // Update UI with current state
        this.updateProgress();

        // Resume playback if it was playing
        if (state.is_playing && !state.is_paused) {
            await this.resumePlayback();
        }
    }
}
```

**User Experience:**
1. User starts listening to "Common Words" (50 cards)
2. Gets to card 20
3. Browser refreshes or navigates away
4. Page reloads → Shows "Resume Listening Session?" prompt ✅
5. User clicks "Resume" → Continues from card 20 ✅

---

## JavaScript Module Organization

### Current Structure (Single File)

```
static/js/
├── tts.js           (650 lines) ← TTS management
├── listening.js     (1070 lines) ← Listening mode
└── mobile.js        (150 lines) ← Mobile utilities
```

**Problems:**
- Hard to navigate large files
- Difficult to test individual components
- Unclear dependencies
- Can't reuse code across features

---

### Target Structure (Modular)

```
static/js/
├── modules/
│   ├── state-manager.js        ← Central state management
│   ├── tts-manager.js          ← TTS core functionality
│   ├── audio-unlock.js         ← Mobile audio unlock
│   ├── listening-player.js     ← Card playback logic
│   ├── listening-ui.js         ← UI updates for listening
│   ├── cache-manager.js        ← TTS cache management
│   └── api-client.js           ← Centralized API calls
├── tts.js                      ← Entry point (imports modules)
├── listening.js                ← Entry point (imports modules)
└── mobile.js                   ← Mobile-specific code
```

**Benefits:**
- Single Responsibility Principle
- Easier to test
- Clear dependencies
- Reusable components

---

### Module Implementation Pattern

**Example: Extract TTS Cache to Module**

New file: `static/js/modules/cache-manager.js`

```javascript
/**
 * TTS Cache Manager - Handles audio cache persistence
 */
export class CacheManager {
    constructor(storageKey = 'tts_cache_v1') {
        this.storageKey = storageKey;
        this.cache = new Map();
        this.restore();
    }

    /**
     * Restore cache from localStorage
     */
    restore() {
        try {
            const stored = localStorage.getItem(this.storageKey);
            if (stored) {
                this.cache = new Map(JSON.parse(stored));
                console.log(`💾 Restored ${this.cache.size} cached items`);
            }
        } catch (error) {
            console.warn('⚠️ Cache restore failed:', error);
        }
    }

    /**
     * Save cache to localStorage
     */
    save() {
        try {
            const serialized = JSON.stringify([...this.cache]);
            localStorage.setItem(this.storageKey, serialized);
        } catch (error) {
            console.warn('⚠️ Cache save failed:', error);
            // Likely quota exceeded - clear old entries
            this.evictOldest(10);
            this.save(); // Retry
        }
    }

    /**
     * Get cached item
     */
    get(key) {
        return this.cache.get(key);
    }

    /**
     * Set cached item
     */
    set(key, value) {
        this.cache.set(key, value);
        this.save();
    }

    /**
     * Check if item is cached
     */
    has(key) {
        return this.cache.has(key);
    }

    /**
     * Clear all cache
     */
    clear() {
        this.cache.clear();
        localStorage.removeItem(this.storageKey);
        console.log('🗑️ Cache cleared');
    }

    /**
     * Evict oldest entries (LRU-style)
     */
    evictOldest(count) {
        const entries = [...this.cache.entries()];
        entries.slice(0, count).forEach(([key]) => {
            this.cache.delete(key);
        });
        console.log(`🗑️ Evicted ${count} oldest cache entries`);
    }

    /**
     * Get cache statistics
     */
    getStats() {
        let memoryKB = 0;
        for (const [key, value] of this.cache) {
            memoryKB += (key.length * 2 + value.length * 0.75) / 1024;
        }

        return {
            size: this.cache.size,
            memoryKB: Math.round(memoryKB),
        };
    }
}
```

**Update `static/js/tts.js` to use module:**

```javascript
import { CacheManager } from './modules/cache-manager.js';

class TTSManager {
    constructor() {
        // Use CacheManager instead of inline implementation
        this.cacheManager = new CacheManager('tts_cache_v1');

        // Existing code...
    }

    async speakCard(word, example, voice) {
        // Check cache using CacheManager
        const wordKey = this.getCacheKey(word, voice);

        if (this.cacheManager.has(wordKey)) {
            console.log('🎯 Cache hit');
            return this.cacheManager.get(wordKey);
        }

        // Fetch and cache
        const audio = await this.fetchAudio(word, voice);
        this.cacheManager.set(wordKey, audio);

        return audio;
    }
}

// Export for use in other modules
export { TTSManager };

// Global instance for legacy code
window.ttsManager = new TTSManager();
```

**Use ES Modules in HTML:**

```html
<!-- base.html -->
<script type="module" src="{{ url_for('static', filename='js/tts.js') }}"></script>
<script type="module" src="{{ url_for('static', filename='js/listening.js') }}"></script>
```

**Browser Support:** All modern browsers support ES modules natively. No build step needed!

---

## State Synchronization Patterns

### Pattern 1: Optimistic Updates

Update UI immediately, sync to server in background.

```javascript
// Update local state + UI immediately
window.stateManager._setLocal('listening.current_index', 5);
this.updateProgress();

// Sync to server in background (don't await)
window.stateManager.syncToServer('listening.current_index', 5)
    .catch(error => {
        console.error('Sync failed, will retry:', error);
        // TODO: Add to retry queue
    });
```

**Use Cases:**
- Card navigation (every second)
- Progress updates
- Pause/resume actions

**Benefits:**
- Responsive UI (no waiting for server)
- Graceful degradation if server slow

---

### Pattern 2: Pessimistic Updates

Wait for server confirmation before updating UI.

```javascript
// Show loading state
this.showLoading(true);

// Update server first (await)
await window.stateManager.set('listening.tab_name', 'New Tab');

// Update UI only after success
this.updateTabDisplay('New Tab');
this.showLoading(false);
```

**Use Cases:**
- Starting new session (critical operation)
- Ending session (important state change)
- User authentication

**Benefits:**
- Guaranteed consistency
- Clear error handling

---

### Pattern 3: Polling for Updates

Periodically check server for state changes (for multi-tab sync).

```javascript
class StateManager {
    constructor() {
        // Poll server every 5 seconds for changes
        this.startPolling();
    }

    startPolling() {
        setInterval(async () => {
            await this.refreshFromServer();
        }, 5000);
    }

    async refreshFromServer() {
        try {
            const response = await fetch('/api/state/all');
            const data = await response.json();

            if (data.success) {
                // Check for differences
                if (JSON.stringify(this.state) !== JSON.stringify(data.state)) {
                    console.log('🔄 State changed on server, updating local');
                    this.state = data.state;
                    this.notifyListeners('*', this.state);
                }
            }
        } catch (error) {
            console.warn('⚠️ Polling failed:', error);
        }
    }
}
```

**Use Cases:**
- Multi-tab synchronization
- Collaborative features (future)
- Server-side state changes

---

### Pattern 4: Conflict Resolution

Handle conflicts when client and server disagree.

```javascript
async syncToServer(path, value) {
    const response = await fetch('/api/state/listening', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            ...value,
            client_timestamp: Date.now(),
            client_version: this.state.listening?.version || 0
        })
    });

    const data = await response.json();

    if (data.conflict) {
        // Server has newer version
        console.warn('⚠️ Conflict detected, resolving...');

        // Strategy 1: Server wins (simple)
        this.state.listening = data.server_state;
        this.notifyListeners('listening', data.server_state);

        // Strategy 2: Merge (complex)
        // const merged = this.mergeStates(this.state.listening, data.server_state);
        // this.state.listening = merged;
    }
}
```

---

## Error Handling & Recovery

### Network Failure Handling

```javascript
class StateManager {
    constructor() {
        this.syncQueue = [];
        this.isOnline = navigator.onLine;

        // Listen for online/offline events
        window.addEventListener('online', () => this.onOnline());
        window.addEventListener('offline', () => this.onOffline());
    }

    onOffline() {
        console.log('📡 Network offline, queuing updates');
        this.isOnline = false;
    }

    async onOnline() {
        console.log('📡 Network online, syncing queued updates');
        this.isOnline = true;

        // Sync all queued updates
        while (this.syncQueue.length > 0) {
            const update = this.syncQueue.shift();
            await this.syncToServer(update.path, update.value);
        }
    }

    async syncToServer(path, value) {
        if (!this.isOnline) {
            // Queue for later
            this.syncQueue.push({ path, value });
            console.log('⏳ Update queued (offline)');
            return;
        }

        // Normal sync logic...
    }
}
```

---

### State Corruption Recovery

```javascript
class StateManager {
    /**
     * Validate state structure
     */
    validateState(state) {
        // Define expected structure
        const schema = {
            listening: {
                required: ['tab_name', 'current_index', 'total_count'],
                types: {
                    tab_name: 'string',
                    current_index: 'number',
                    total_count: 'number'
                }
            }
        };

        // Validate each namespace
        for (const [namespace, rules] of Object.entries(schema)) {
            if (!state[namespace]) continue;

            // Check required fields
            for (const field of rules.required) {
                if (!(field in state[namespace])) {
                    throw new Error(`Missing required field: ${namespace}.${field}`);
                }
            }

            // Check types
            for (const [field, expectedType] of Object.entries(rules.types)) {
                const actualType = typeof state[namespace][field];
                if (actualType !== expectedType) {
                    throw new Error(`Invalid type: ${namespace}.${field} should be ${expectedType}, got ${actualType}`);
                }
            }
        }
    }

    /**
     * Recover from corrupted state
     */
    async recoverState() {
        console.error('❌ State corrupted, recovering from server...');

        try {
            // Fetch fresh state from server
            const response = await fetch('/api/state/all');
            const data = await response.json();

            if (data.success) {
                this.state = data.state;
                this.validateState(this.state);
                console.log('✅ State recovered from server');
                return true;
            }
        } catch (error) {
            console.error('💥 Recovery failed:', error);
        }

        // Last resort: clear state
        this.state = { listening: null, learning: null, user: null };
        console.log('🧹 State reset to empty');
        return false;
    }
}
```

---

## Testing Strategy

### Unit Tests

Test StateManager in isolation:

```javascript
// tests/state-manager.test.js
import { StateManager } from '../static/js/modules/state-manager.js';

describe('StateManager', () => {
    let stateManager;

    beforeEach(() => {
        stateManager = new StateManager();
        // Mock fetch for testing
        global.fetch = jest.fn();
    });

    test('get returns correct value', () => {
        stateManager._setLocal('listening.current_index', 5);
        expect(stateManager.get('listening.current_index')).toBe(5);
    });

    test('set updates local state', () => {
        stateManager.set('listening.is_playing', true, { syncToServer: false });
        expect(stateManager.get('listening.is_playing')).toBe(true);
    });

    test('subscribe notifies listeners', (done) => {
        stateManager.subscribe('listening.current_index', (value) => {
            expect(value).toBe(10);
            done();
        });

        stateManager.set('listening.current_index', 10, { syncToServer: false });
    });

    test('sync calls correct API endpoint', async () => {
        global.fetch.mockResolvedValue({
            json: async () => ({ success: true })
        });

        await stateManager.syncToServer('listening', { current_index: 5 });

        expect(global.fetch).toHaveBeenCalledWith(
            '/api/state/listening',
            expect.objectContaining({ method: 'POST' })
        );
    });
});
```

---

### Integration Tests

Test StateManager with real backend:

```javascript
// tests/integration/state-sync.test.js
describe('State Synchronization', () => {
    test('listening state syncs to server', async () => {
        // Start listening session
        await window.listeningManager.startListening('Common Words');

        // Verify state in StateManager
        const state = window.stateManager.get('listening');
        expect(state.tab_name).toBe('Common Words');

        // Verify state on server
        const response = await fetch('/api/state/listening');
        const serverState = await response.json();
        expect(serverState.state.tab_name).toBe('Common Words');
    });

    test('state persists across page reload', async () => {
        // Set state
        await window.stateManager.set('listening', {
            tab_name: 'Test',
            current_index: 5
        });

        // Simulate page reload
        window.location.reload();
        await new Promise(resolve => setTimeout(resolve, 1000));

        // Verify state restored
        const state = window.stateManager.get('listening');
        expect(state.current_index).toBe(5);
    });
});
```

---

## Migration Checklist

### Phase 1: StateManager Foundation (Week 1)
- [ ] Create `static/js/modules/state-manager.js`
- [ ] Add state initialization from server
- [ ] Implement get/set/subscribe methods
- [ ] Add sync-to-server logic
- [ ] Write unit tests for StateManager
- [ ] Add to page templates with `<script type="module">`

### Phase 2: Backend State API (Week 2)
- [ ] See `backend-cleanup.md` Phase 2
- [ ] Create `/api/state/listening` endpoints
- [ ] Create `/api/state/learning/progress` endpoints
- [ ] Add Pydantic validation models
- [ ] Test API endpoints

### Phase 3: Refactor ListeningManager (Week 3)
- [ ] Update ListeningManager to use StateManager
- [ ] Remove local state storage (currentSession, cards, etc.)
- [ ] Add state subscriptions
- [ ] Implement session recovery on page load
- [ ] Test listening mode with state persistence
- [ ] Verify audio cleanup works correctly

### Phase 4: Extract Modules (Week 4)
- [ ] Extract `modules/cache-manager.js` from tts.js
- [ ] Extract `modules/audio-unlock.js` from tts.js
- [ ] Extract `modules/listening-player.js` from listening.js
- [ ] Extract `modules/api-client.js` for centralized API calls
- [ ] Update entry point files to import modules
- [ ] Test all modules independently

### Phase 5: Polish & Documentation (Week 5)
- [ ] Add error handling and recovery
- [ ] Add network offline support
- [ ] Add state validation
- [ ] Write integration tests
- [ ] Document state management patterns
- [ ] Update README with architecture diagram

---

## Success Metrics

**Code Quality:**
- [ ] All state access through StateManager
- [ ] No more operation tokens
- [ ] JavaScript files < 300 lines each
- [ ] Clear module boundaries

**Functionality:**
- [ ] Listening state survives page reload
- [ ] Can resume interrupted sessions
- [ ] No ghost audio after navigation
- [ ] Sync works offline (queued)

**Performance:**
- [ ] State sync < 100ms
- [ ] No UI blocking during sync
- [ ] Cache hit rate > 90%
- [ ] Memory usage stable (no leaks)

---

## Future Enhancements

### Multi-Tab Synchronization
- Share state across browser tabs
- Notify other tabs of state changes
- Use BroadcastChannel API

### Offline Mode
- Full offline support with service workers
- Queue all state changes
- Sync when online

### Collaborative Features
- Multiple users learning together
- Shared listening sessions
- Real-time progress updates via WebSockets

### Analytics
- Track listening session completion rates
- Identify most-played cards
- Generate learning insights

---

## Questions / Discussion

**Before Starting:**
- Should we support multi-tab sync in Phase 1?
- How long should we keep state in server session? (TTL?)
- Should we add version numbers to state for conflict resolution?
- Do we need to support IE11? (affects module strategy)

**Add your notes here as you implement:**
- [ ] Phase 1 notes:
- [ ] Phase 2 notes:
- [ ] Phase 3 notes:
- [ ] Phase 4 notes:
- [ ] Phase 5 notes:

---

## Related Documentation

- See `backend-cleanup.md` for server-side state management
- See `listening-mode.md` for current listening mode architecture
- See `tts-system.md` for TTS implementation details
