# 🎵 Listening Mode Feature Plan

## 📋 Feature Overview
Add "Listen" buttons to card sets on the main page that play through ALL cards sequentially with Portuguese audio (word → example → next card), with background playback support for mobile devices.

## 🎯 Core Requirements
- ✅ **Shuffle cards** before every playback session
- ✅ **No progress persistence** - always start fresh
- ✅ **Play all cards** from card set (not just review cards)
- ✅ **Background playback** support for locked phones
- ✅ **Smart caching** - preload next cards during playback
- ✅ **Mobile optimization** - notification controls, media session API

## 📅 Implementation Phases

### 🔴 Phase 1: Basic Sequential Playback (PLANNED)
**Goal**: Get basic listening functionality working

#### Backend Changes
- [ ] **1.1** Add API endpoint `GET /api/cards/<tab_name>` in `src/routes/api.py`
  - Return shuffled cards with `word` and `example` fields
  - Include metadata: `tab_name`, `total_count`, `sheet_gid`
  - Use existing `read_card_set()` function
  - Always shuffle with `random.shuffle()`

#### Frontend Changes
- [ ] **1.2** Update `templates/index.html`
  - Add "Listen" button next to each "Study" button
  - Button with `data-tab-name` and `data-card-count` attributes
  - Use Bootstrap flex layout for button group

- [ ] **1.3** Create `static/js/listening.js`
  - `ListeningManager` class for session management
  - `startListening(tabName)` - fetch cards and begin playback
  - `playNextCard()` - sequential card playback logic
  - Integration with existing `TTSManager`

- [ ] **1.4** Update `templates/index.html` scripts
  - Include `listening.js`
  - Initialize listen button click handlers
  - Connect to existing TTS infrastructure

#### Progress UI
- [ ] **1.5** Add playback progress display
  - Show current card info: "Playing: casa (5/150)"
  - Progress bar with percentage
  - Pause/Resume and Stop buttons

**Definition of Done**: User can click "Listen" button and hear all cards in a set played sequentially

---

### 🟡 Phase 2: Smart Caching & Performance (PLANNED)
**Goal**: Optimize performance with background caching

#### Caching Strategy
- [ ] **2.1** Implement preloading in `ListeningManager`
  - Cache next 2-3 cards while current card plays
  - Use existing `TTSManager.speakCard()` with `autoplay=false`
  - Manage cache memory to prevent bloat

- [ ] **2.2** Background caching optimization
  - Start caching immediately after API response
  - Cache during 1-second delays between word/example
  - Implement cache eviction for old cards

#### Error Handling
- [ ] **2.3** Robust error handling
  - Skip cards without audio gracefully
  - Network failure recovery
  - TTS service unavailable fallbacks

**Definition of Done**: Smooth playback with no delays between cards, smart memory management

---

### 🟢 Phase 3: Background Playback Support (PLANNED)
**Goal**: Enable playback when phone is locked

#### Media Session API Integration
- [ ] **3.1** Implement Media Session API in `listening.js`
  - Set media metadata for notification controls
  - Handle play/pause/stop from notification area
  - Update now playing info for each card

- [ ] **3.2** Service Worker enhancements in `static/sw.js`
  - Handle background audio requests
  - Cache audio data for offline playback
  - Maintain playback state across page visibility changes

#### Mobile Optimizations
- [ ] **3.3** Wake Lock API integration (where supported)
  - Prevent screen sleep during active listening
  - Graceful fallback for unsupported browsers

- [ ] **3.4** Audio focus management
  - Handle phone calls and other app interruptions
  - Resume playback after interruption ends
  - Proper audio session management

**Definition of Done**: Listening continues when phone is locked, with notification controls working

---

### 🔵 Phase 4: Enhanced UX Features (PLANNED)
**Goal**: Polish the user experience

#### Advanced Controls
- [ ] **4.1** Playback speed control
  - 0.5x, 1x, 1.5x, 2x speed options
  - Maintain speed setting across cards
  - Speed control in notification area

- [ ] **4.2** Skip/navigation controls
  - Skip to next/previous card
  - Jump to specific card number
  - Restart current card

#### Visual Enhancements
- [ ] **4.3** Enhanced progress display
  - Animated progress bar
  - Visual card preview (word text)
  - Time remaining estimate

- [ ] **4.4** Audio visualization
  - Simple waveform or audio indicator
  - Visual feedback during playback
  - Loading states for cache warming

**Definition of Done**: Rich, polished listening experience with full mobile support

---

## 🏗️ Technical Architecture

### API Design
```javascript
// GET /api/cards/beginner-vocab
{
  "success": true,
  "tab_name": "Beginner Vocab",
  "sheet_gid": 123456,
  "cards": [
    {"id": 1, "word": "casa", "example": "Eu vivo numa casa pequena"},
    {"id": 2, "word": "carro", "example": "O meu carro é azul"}
    // ... shuffled order
  ],
  "total_count": 150
}
```

### JavaScript Classes
```javascript
class ListeningManager {
  constructor()
  async startListening(tabName)
  async playNextCard()
  async preloadCards(startIndex, count)
  pausePlayback()
  resumePlayback()
  stopPlayback()
}
```

### Media Session Integration
```javascript
navigator.mediaSession.metadata = new MediaMetadata({
  title: currentCard.word,
  artist: "Portuguese Learning",
  album: tabName,
  artwork: [...]
});
```

## 🔧 File Changes Required

### New Files
- [ ] `LISTENING_MODE_PLAN.md` (this file)
- [ ] `static/js/listening.js`

### Modified Files
- [ ] `src/routes/api.py` - Add cards endpoint
- [ ] `templates/index.html` - Add listen buttons and scripts
- [ ] `static/sw.js` - Background playback support
- [ ] `static/css/style.css` - Listening UI styles

## 🧪 Testing Strategy

### Manual Testing
- [ ] Desktop browser playback
- [ ] Mobile browser playback
- [ ] Background playback (phone locked)
- [ ] Notification controls
- [ ] Network interruption recovery
- [ ] Large card sets (100+ cards)

### Edge Cases
- [ ] No audio available for some cards
- [ ] TTS service temporarily unavailable
- [ ] Network connectivity issues
- [ ] Battery optimization interference
- [ ] Multiple tabs with listening sessions

## 📱 Mobile Background Playback Notes

**Technical Challenges**:
- iOS Safari has strict autoplay policies
- Android Chrome requires user interaction for background audio
- Battery optimization may kill background processes

**Solutions**:
- Media Session API for notification controls
- Service Worker for background processing
- Wake Lock API to prevent sleep (where supported)
- Proper audio context management
- User interaction detection and audio unlocking

**Browser Support**:
- ✅ Chrome Android: Media Session API supported
- ✅ Firefox Android: Partial support
- ⚠️ iOS Safari: Limited background support
- ✅ Samsung Internet: Full support

---

## 📊 Progress Tracking

**Current Status**: ✅ Phase 1 - Complete! 🎉
**Next Step**: Ready for Phase 2 - Smart Caching & Performance

**Completed**:
- [x] Feature planning and architecture design
- [x] **1.1** Add API endpoint `GET /api/cards/<tab_name>` in `src/routes/api.py`
- [x] **1.2** Update `templates/index.html` - Add Listen buttons and progress modal
- [x] **1.3** Create `static/js/listening.js` - ListeningManager class
- [x] **1.4** Update `templates/index.html` scripts - Connect ListeningManager to buttons
- [x] **1.5** Add playback progress display - All UI features implemented

**In Progress**:
- [ ] None - Phase 1 Complete!

**Blocked**:
- [ ] None
