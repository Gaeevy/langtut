/**
 * Card page JavaScript
 * Handles card interactions, keyboard navigation, and TTS prefetching
 */

// Track prefetch attempts to prevent duplicates
let prefetchAttempted = false;

/**
 * Card flipping functionality for review mode
 */
function flipCard() {
    if (window.cardMode === 'review' && window.reviewFlipUrl) {
        window.location.href = window.reviewFlipUrl;
    }
}

/**
 * Toggle equivalent content visibility
 */
function toggleEquivalent() {
    const content = document.getElementById('equivalent-content');
    const button = document.querySelector('.equivalent-toggle button');

    if (!content || !button) return;

    if (content.style.display === 'none' || content.style.display === '') {
        content.style.display = 'block';
        button.innerHTML = '<i class="bi bi-eye-slash"></i> Hide hint';
    } else {
        content.style.display = 'none';
        button.innerHTML = '<i class="bi bi-eye"></i> Show hint';
    }
}

/**
 * TTS prefetching for current card
 */
async function prefetchCardTTS() {
    if (!window.ttsManager) {
        console.log('⏭️ Skipping prefetch - TTS manager not available');
        return;
    }

    // Wait for TTS service to be ready (fixes race condition)
    const ready = await window.ttsManager.waitForService();
    if (!ready) {
        console.log('⏭️ Skipping prefetch - TTS service not available');
        return;
    }

    console.log('🔄 Prefetching TTS for current card...');
    await window.ttsManager.speakCard(
        window.cardData.word,
        window.cardData.example,
        false,  // autoplay = false (just prefetch)
        window.cardContext.spreadsheetId,
        window.cardContext.sheetGid
    );
    console.log('✅ Prefetch complete');
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
 * Initialize card page
 */
function initCardPage() {
    // Focus answer input for learn mode
    if (window.cardMode === 'learn') {
        const answerInput = document.querySelector('input[name="user_answer"]');
        if (answerInput) {
            answerInput.focus();
        }
    }

    // Setup keyboard navigation
    setupKeyboardNavigation();

    // Start TTS prefetching
    prefetchCardTTS();
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initCardPage);

// Play button handler
document.querySelector('.play-button')?.addEventListener('click', async () => {
    console.log('🎵 Play button clicked');
    await window.ttsManager.speakCard(
        window.cardData.word,
        window.cardData.example,
        true,  // autoplay = true
        window.cardContext.spreadsheetId,
        window.cardContext.sheetGid
    );
});

window.addEventListener('beforeunload', () => {
    if (window.ttsManager) {
        window.ttsManager.cleanupForPageUnload();
    }
});
