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

- **TTS Service** (`app/services/tts.py`) -- wraps Google Cloud TTS API, caches audio in a GCS bucket (`langtut-tts`), returns base64-encoded MP3
- **API endpoints** (`app/routes/api/tts.py`):
  - `GET /api/tts/status` -- check if TTS is available
  - `POST /api/tts/speak` -- generate audio for a text string. Request: `{"text": "olá"}`. Response: `{"success": true, "audio_base64": "..."}`

### Frontend

- **TTSManager** (`app/static/js/tts.js`) -- singleton that handles:
  - Fetching audio from `/api/tts/speak` with deduplication of in-flight requests
  - Client-side caching in `localStorage` (base64 keyed by text)
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

Listening mode uses a modal with an explicit "Start" button. On Chrome iOS, clicking this button creates a "primed" `Audio` element that can be reused for all subsequent playback:

```
User taps "Start" → unlockAudioForChromeIOS() → creates Audio element,
loads silent WAV → stores as primedAudioForChromeIOS → all subsequent
playAudio() calls reuse this element by swapping its src
```

Other browsers use `AudioContext.resume()` + silent buffer playback.

### Browser Summary

| Browser | Unlock method | Notes |
|---------|--------------|-------|
| Chrome iOS | Primed Audio element during gesture | Most restrictive |
| Safari iOS | AudioContext resume + silent buffer | Standard mobile pattern |
| Android Chrome | AudioContext resume | Standard mobile pattern |
| Desktop | None needed | Auto-unlocked |

## Caching

### Server-side (GCS)

Audio is cached in a GCS bucket keyed by text + voice + language. Avoids re-calling Google Cloud TTS for previously generated audio.

### Client-side (localStorage)

`TTSManager` caches base64 audio in `localStorage` keyed by text. This survives page reloads and means repeated cards play instantly without network requests. The `pendingRequests` Map deduplicates concurrent fetches for the same text.

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
