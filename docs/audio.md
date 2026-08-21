# Audio System

## Overview

The audio system provides TTS (text-to-speech) for language learning. It covers two main use cases:

1. **Card feedback autoplay** -- after answering a card, the word and example sentence play automatically
2. **Listening mode** -- sequential playback of all cards in a set, with infinite loop

## Architecture

```
User interaction
    ↓
card.js / listening.js
    ↓
TTSManager (tts.js)  ←→  localStorage cache
    ↓
POST /api/tts/speak  ←→  GCS audio cache
    ↓
Google Cloud TTS API
```

### Backend

- **TTS Service** (`app/services/tts.py`) -- wraps Google Cloud TTS API, caches audio in the configured GCS bucket, returns base64-encoded MP3
- **API endpoints** (`app/routes/api/tts.py`):
  - `GET /api/tts/status` -- check if TTS is available
  - `POST /api/tts/speak` -- generate audio for a text string. Request: `{"text": "olá"}`. Response: `{"success": true, "audio_base64": "..."}`
  - `POST /api/tts/invalidate` -- delete one authenticated user's cached GCS clip so the next speak request regenerates it

### Frontend

- **TTSManager** (`app/static/js/tts.js`) -- singleton that handles:
  - Fetching audio from `/api/tts/speak` with deduplication of in-flight requests
  - Client-side caching in `localStorage` (base64 keyed by trimmed text only; simple and fast; rare stale clip if target language or voice changes until cache cleared)
  - Audio playback via HTML5 `Audio` elements
  - Mobile browser detection and audio unlock strategies
  - Chrome iOS "primed audio element" reuse
- **card.js** -- card page: prefetches audio on load, AJAX answer submission with in-page feedback and audio autoplay
- **feedback.js** -- fallback for direct feedback page loads (refresh, bookmarks)
- **listening.js** -- `ListeningManager` for sequential card playback in a modal

## Mobile Autoplay

Mobile browsers (especially Chrome iOS) block `audio.play()` unless it happens within a user gesture. This is the central challenge.

### Card Feedback (AJAX approach)

The card→feedback transition uses AJAX instead of a full page navigation. This keeps everything in the same page context, preserving the user gesture:

1. User clicks Submit (user gesture)
2. `card.js` intercepts the form `submit` event
3. Unlocks audio (creates primed element on Chrome iOS)
4. Plays word+example audio from prefetch cache -- still within gesture context
5. Submits answer via `fetch('/learn/answer', {json})` in parallel
6. Renders feedback UI in-page (no reload)
7. `history.replaceState` updates URL so refresh loads server-rendered feedback

If the fetch fails, the form falls back to a normal POST (original behavior). The server-rendered `feedback.html` + `feedback.js` still works for direct page loads.

### Listening Mode (primed element approach)

Listening mode uses a modal with an explicit "Start" button. On mobile, that tap runs `TTSManager.unlockAudio()`, which primes a single `HTMLAudioElement` (silent WAV `load()` during the gesture). All later TTS clips reuse that element by swapping `src` to MP3 data URLs. Without this reuse, **Safari iOS** often allows the first `play()` after an AudioContext-only unlock, then throws `NotAllowedError` on the next `new Audio().play()` (e.g. example after word).

```
User taps Start → unlockAudio() → AudioContext (where supported) + primed Audio element
→ playAudio() swaps src on the same element for word, example, and every card
```

### Browser Summary

| Browser | Unlock method | Notes |
|---------|--------------|-------|
| Chrome iOS | Primed `Audio` during gesture | Required for autoplay |
| Safari iOS | AudioContext + **same primed `Audio`** | AudioContext alone is not enough for sequential clips |
| Android Chrome | AudioContext + primed `Audio` | Harmless extra priming |
| Desktop | None needed | Auto-unlocked; always `new Audio()` |

## Caching

### Server-side (GCS)

When the request includes both a spreadsheet ID and sheet GID, audio is cached below
`<spreadsheet-id>/<sheet-gid>/` using a hash of text + voice + language. Requests without both
identifiers still generate audio, but do not use the GCS cache.

### Client-side (localStorage)

`TTSManager` caches base64 audio in `localStorage` under key `tts_cache`, keyed by **trimmed text only**. Entries expire after 24 hours and are evicted least-recently-used when their estimated localStorage footprint exceeds 4 MiB. The versioned payload discards the old metadata-free, unbounded cache on upgrade. The `pendingRequests` Map deduplicates concurrent fetches for the same text key.

The feedback card's small regenerate control removes both the word and example from the browser cache, calls the authenticated invalidation endpoint for their voice-specific GCS objects, and immediately fetches and plays fresh clips. Missing GCS objects are treated as an idempotent no-op.

### Prefetching

On the card page, `prefetchCardTTS()` fires on page load to cache the current card's word and example audio before the user answers. In listening mode, the next card is prefetched in the background while the current one plays.

## Listening Mode

Sequential playback of all cards in a vocabulary tab:

1. Fetch cards from `/api/cards/<tab_name>`
2. Play each card (word → 1s pause → example)
3. After all cards: increment loop counter, Fisher-Yates reshuffle, repeat
4. Operation tokens prevent ghost playback from stale sessions

Controls: pause/resume, progress bar, loop counter, modal close stops everything.

## Key Files

| File | Role |
|------|------|
| `app/services/tts.py` | Google Cloud TTS client + GCS caching |
| `app/routes/api/tts.py` | `/api/tts/speak` and `/api/tts/status` endpoints |
| `app/routes/learn.py` | `/learn/answer` supports JSON for AJAX |
| `app/static/js/tts.js` | TTSManager: fetch, cache, play, mobile unlock |
| `app/static/js/card.js` | AJAX submission, prefetch, in-page feedback |
| `app/static/js/feedback.js` | Fallback for server-rendered feedback pages |
| `app/static/js/listening.js` | ListeningManager for sequential playback |
| `app/static/js/modes.js` | pick_one / build modes (uses `requestSubmit`) |

## Configuration

```toml
# settings.toml
tts_enabled = true
tts_audio_encoding = "MP3"
gcs_audio_bucket = "langtut-tts"
```

Voice is resolved from the user's target language setting stored in session.

Supported language/voice pairs live in `config/languages.yaml`. The target language is copied to
the `tts.*` session namespace from the active spreadsheet's language settings when the dashboard,
learn flow, or review flow is entered.

## Manual verification checklist

Automated tests cover templates and static JS contracts; they cannot prove iOS Chrome gesture audio. After any audio refactor, verify manually:

**Desktop (Chrome or Firefox)**

1. Learn: open a card, submit an answer — word and example audio play on feedback without clicking the speaker.
2. Tap the speaker button on feedback — audio plays again.
3. Home: open Listen for a tab — start playback, pause, resume, close modal — no audio continues after close.

**iOS Safari**

1. Same as desktop; on first visit you may need one tap anywhere to unlock (first-interaction handler).
2. Refresh on a learn feedback URL — audio may require a tap (expected for non-AJAX loads).

**iOS Chrome (CriOS)**

1. Learn: submit an answer — audio should play immediately after submit (AJAX path + cache prefetch).
2. If prefetch missed, audio should still play via primed `Audio` fallback after the response.
3. Listen: tap unlock/start — sequential word → example playback; closing the modal stops audio.

If any step fails, capture user agent and whether the issue is silent playback vs. delayed playback only.
