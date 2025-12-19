/**
 * Feedback page JavaScript
 * Handles level animations, TTS playback, and keyboard navigation
 */

// Track if we've attempted to unlock audio
let unlockAttempted = false;

/**
 * Unlock audio on first user interaction (critical for iOS)
 */
async function unlockAudioOnFirstInteraction() {
    if (unlockAttempted || !window.ttsManager) {
        return;
    }

    // Only unlock if not already unlocked
    // Trust the session storage - iOS remembers domain unlock across pages
    if (window.ttsManager.isUnlocked()) {
        unlockAttempted = true;
        return;
    }

    unlockAttempted = true;
    console.log('🔓 Attempting to unlock audio on first interaction...');

    try {
        const success = await window.ttsManager.unlockAudio();
        if (success) {
            console.log('✅ Audio unlocked successfully on first interaction');
            // After unlocking, retry TTS auto-play if card data is available
            const cardDataElement = document.getElementById('card-data');
            if (cardDataElement) {
                const cardData = JSON.parse(cardDataElement.textContent);
                setTimeout(async () => {
                    const ready = await window.ttsManager.waitForService();
                    if (ready) {
                        window.ttsManager.speakCard(
                            cardData.word,
                            cardData.example,
                            true,
                            cardData.spreadsheetId,
                            cardData.sheetGid
                        );
                    }
                }, 300);
            }
        } else {
            console.warn('⚠️ Audio unlock failed on first interaction');
        }
    } catch (error) {
        console.error('❌ Error unlocking audio:', error);
    }
}

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
    // iOS remembers domain unlock across pages, so new Audio elements will work
    if (window.ttsManager.isUnlocked()) {
        console.log('✅ Audio unlocked - auto-playing card audio');
        setTimeout(async () => {
            // Wait for TTS service to be ready
            const ready = await window.ttsManager.waitForService();
            if (ready) {
                window.ttsManager.speakCard(word, example, true, spreadsheetId, sheetGid);
            } else {
                console.log('⚠️ TTS service not available - skipping auto-play');
            }
        }, 300);
    } else {
        console.log('⚠️ Audio not unlocked - skipping auto-play (will unlock on first click)');
    }

    // Setup speak button click handler
    const speakButton = document.getElementById('speak-card-btn');
    if (speakButton) {
        speakButton.addEventListener('click', async function() {
            if (!window.ttsManager.isUnlocked()) {
                console.log('🔓 Unlocking audio from button click...');
                await window.ttsManager.unlockAudio();
            }
            // Wait for TTS service to be ready
            const ready = await window.ttsManager.waitForService();
            if (ready) {
                window.ttsManager.speakCard(word, example, true, spreadsheetId, sheetGid);
            } else {
                console.log('⚠️ TTS service not available');
            }
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

    // Add first-click unlock handler for mobile
    // This ensures audio is unlocked during the FIRST user interaction
    const unlockOnFirstClick = async (event) => {
        await unlockAudioOnFirstInteraction();
        // Remove listener after first click
        document.removeEventListener('click', unlockOnFirstClick);
        document.removeEventListener('touchstart', unlockOnFirstClick);
    };
    document.addEventListener('click', unlockOnFirstClick, { once: true });
    document.addEventListener('touchstart', unlockOnFirstClick, { once: true });

    // Level progression animation - only for learn mode
    if (mode === 'learn') {
        animateLevelChange(level, levelChange);
    }

    // Setup TTS
    setupTTS(cardData);
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initFeedbackPage);

window.addEventListener('beforeunload', () => {
    if (window.ttsManager) {
        window.ttsManager.cleanupForPageUnload();
    }
});
