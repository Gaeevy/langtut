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
 * Simplified TTS prefetching functionality
 */
async function prefetchCardTTS() {
    // Prevent duplicate prefetching
    if (prefetchAttempted) {
        return;
    }

    // Check if TTS manager is available
    if (typeof window.ttsManager === 'undefined') {
        return;
    }

    // Check if we have data to prefetch
    if (!window.cardData || (!window.cardData.word && !window.cardData.example)) {
        return;
    }

    // Set flag to prevent duplicate attempts
    prefetchAttempted = true;

    try {
        // Trigger TTS generation (cache only, no autoplay)
        await window.ttsManager.speakCard(
            window.cardData.word,
            window.cardData.example,
            null, // voice name
            false, // autoplay = false (just cache)
            window.cardContext.spreadsheetId,
            window.cardContext.sheetGid
        );
    } catch (error) {
        console.error('💥 Prefetch error:', error);
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
