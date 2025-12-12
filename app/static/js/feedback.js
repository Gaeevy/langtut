/**
 * Feedback page JavaScript
 * Handles level animations, TTS playback, and keyboard navigation
 */

/**
 * Card flipping functionality for review mode (flip back to face)
 */
function flipCard() {
    if (window.cardMode === 'review' && window.reviewCardUrl) {
        window.location.href = window.reviewCardUrl;
    }
}

/**
 * Setup keyboard navigation for review mode
 */
function setupKeyboardNavigation() {
    document.addEventListener('keydown', function(event) {
        if (window.cardMode === 'review') {
            switch(event.key) {
                case 'ArrowLeft':
                    event.preventDefault();
                    const prevBtn = document.getElementById('nav-prev');
                    if (prevBtn) prevBtn.click();
                    break;
                case 'ArrowRight':
                    event.preventDefault();
                    const nextBtn = document.getElementById('nav-next');
                    if (nextBtn) nextBtn.click();
                    break;
                case ' ':
                    event.preventDefault();
                    flipCard();
                    break;
            }
        }
    });
}

/**
 * Animate level progression dots
 */
function animateLevelChange(currentLevel, levelChange) {
    if (!levelChange) return;

    console.log('Level change detected:', levelChange);

    const levelDots = document.querySelectorAll('.level-dot');
    if (levelDots.length === 0) return;

    const currentDot = levelDots[currentLevel];
    if (currentDot) {
        currentDot.classList.add('level-changed');
        setTimeout(() => {
            currentDot.classList.remove('level-changed');
        }, 1000);
    }
}

/**
 * Setup TTS auto-play and button handlers
 */
function setupTTS(cardData) {
    if (!window.ttsManager) return;

    const { word, example, spreadsheetId, sheetGid } = cardData;

    // Auto-play if audio is unlocked
    if (window.ttsManager.isUnlocked()) {
        console.log('✅ Audio unlocked - auto-playing card audio');
        setTimeout(() => {
            window.ttsManager.speakCard(word, example, true, spreadsheetId, sheetGid);
        }, 300);
    } else {
        console.log('⚠️ Audio not unlocked - skipping auto-play');
    }

    // Setup speak button click handler
    const speakButton = document.getElementById('speak-card-btn');
    if (speakButton) {
        speakButton.addEventListener('click', async function() {
            if (!window.ttsManager.isUnlocked()) {
                console.log('🔓 Unlocking audio from button click...');
                await window.ttsManager.unlockAudio();
            }
            window.ttsManager.speakCard(word, example, true, spreadsheetId, sheetGid);
        });
    }
}

/**
 * Initialize feedback page
 */
function initFeedbackPage() {
    // Get card data from JSON script tag
    const cardDataElement = document.getElementById('card-data');
    if (!cardDataElement) return;

    const cardData = JSON.parse(cardDataElement.textContent);
    const { correct, level, levelChange, mode } = cardData;

    // Setup keyboard navigation
    setupKeyboardNavigation();

    // Level progression animation - only for learn mode
    if (mode === 'learn') {
        animateLevelChange(level, levelChange);
    }

    // Setup TTS
    setupTTS(cardData);
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initFeedbackPage);
