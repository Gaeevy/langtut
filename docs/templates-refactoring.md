# Templates Refactoring Plan

## Current State Analysis

### File Sizes (Lines)
| Template | Lines | HTML | CSS | JS | Status |
|----------|-------|------|-----|-----|--------|
| base.html | 58 | 58 | 0 | 0 | ✅ Clean |
| index.html | 516 | ~180 | ~300 | ~35 | 🔴 Bloated |
| card.html | 438 | ~130 | ~200 | ~110 | 🔴 Bloated |
| feedback.html | 428 | ~130 | ~200 | ~100 | 🔴 Bloated |
| settings.html | 668 | ? | ? | ? | 🔴 Largest |
| results.html | 79 | ~79 | 0 | 0 | ✅ OK |
| login.html | 28 | ~28 | 0 | 0 | ✅ OK |
| error.html | 17 | ~17 | 0 | 0 | ✅ OK |
| setup.html | 79 | ~79 | 0 | 0 | ✅ OK |
| test_tts.html | 197 | ? | ? | ? | 🟡 Dev only |
| offline.html | 33 | ~33 | 0 | 0 | ✅ OK |

### Problems Identified

1. **CSS Duplication** - Button styles duplicated across 3+ templates (~200 lines each)
2. **Inline CSS** - ~700 lines of CSS embedded in templates
3. **Inline JS** - ~250 lines of JS embedded in templates
4. **Dev code in prod** - eruda debug console loaded for all users
5. **No CSS organization** - 4 CSS files + massive inline = chaos
6. **No shared components** - Same HTML patterns repeated

## Target Architecture

```
static/css/
├── base.css          # Core layout, container, typography
├── components.css    # Cards, progress bars, badges, modals
├── buttons.css       # Unified button system
├── forms.css         # Input, select styling
└── responsive.css    # Mobile/tablet adjustments

static/js/
├── tts.js            # TTS manager (exists)
├── listening.js      # Listening mode (exists)
├── card.js           # Card page logic (NEW)
├── index.js          # Index page logic (NEW)
└── utils.js          # Shared utilities (NEW)

templates/
├── base.html         # Clean base with CSS includes
├── index.html        # ~100 lines (HTML only)
├── card.html         # ~100 lines (HTML only)
├── feedback.html     # ~100 lines (HTML only)
└── ...
```

## Implementation Phases

### Phase 1: Extract Button CSS ✅
- [x] Create `static/css/buttons.css` with unified button system
- [x] Remove inline button CSS from index.html (~200 lines removed)
- [x] Remove inline button CSS from card.html (~90 lines removed)
- [x] Remove inline button CSS from feedback.html (~110 lines removed)
- [x] Add buttons.css to base.html
- [x] Remove eruda debug console from index.html

### Phase 2: Extract Component CSS ✅
- [x] Create `static/css/components.css`
- [x] Move card styling (language-card, card typography)
- [x] Move progress bar styling (pastel progress bars)
- [x] Move badge styling (pastel badges)
- [x] Move form styling
- [x] Update templates (index, card, feedback)

### Phase 3: Extract JavaScript ✅
- [x] Create `static/js/card.js` from card.html scripts (~70 lines)
- [x] Create `static/js/feedback.js` from feedback.html scripts (~100 lines)
- [x] Create `static/js/index.js` from index.html scripts (~35 lines)
- [x] Update templates to use external JS (data passing only inline)

### Phase 4: Cleanup ⬜
- [ ] Remove eruda debug console from production
- [ ] Consolidate remaining inline CSS
- [ ] Review and clean settings.html
- [ ] Test all functionality

## Progress Tracking

| Phase | Status | Date | Notes |
|-------|--------|------|-------|
| Phase 1 | ✅ Complete | 2025-11-28 | ~400 lines of CSS extracted, eruda removed |
| Phase 2 | ✅ Complete | 2025-11-28 | Components CSS extracted |
| Phase 3 | ✅ Complete | 2025-11-28 | ~200 lines JS extracted to 3 files |
| Phase 4 | 🔄 In Progress | 2025-11-28 | Final cleanup and testing |

## Risk Assessment

- **Low Risk**: CSS extraction (visual only)
- **Medium Risk**: JS extraction (functionality depends on it)
- **Test After Each Phase**: Verify study/review/listen modes work
