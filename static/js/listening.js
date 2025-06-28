/**
 * Listening Mode Manager for sequential card playback
 * Integrates with existing TTSManager for Portuguese audio
 * Enhanced with mobile audio unlock strategies
 */

class ListeningManager {
    constructor() {
        this.currentSession = null;
        this.isPlaying = false;
        this.isPaused = false;
        this.currentCardIndex = 0;
        this.cards = [];
        this.tabName = '';
        this.sheetGid = null;
        this.totalCount = 0;
        this.loopCount = 1; // Track which loop we're in

        // Mobile audio management
        this.isMobile = this.detectMobile();
        this.audioUnlocked = false;
        this.audioContext = null;

        // Initialize UI elements
        this.initializeUI();
    }

    /**
     * Detect if running on mobile device
     */
    detectMobile() {
        return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    }

    /**
     * Initialize UI event handlers
     */
    initializeUI() {
        // Pause/Resume button
        const pauseResumeBtn = document.getElementById('pauseResumeBtn');
        if (pauseResumeBtn) {
            pauseResumeBtn.addEventListener('click', () => {
                if (this.isPaused) {
                    this.resumePlayback();
                } else {
                    this.pausePlayback();
                }
            });
        }

        // Modal close handler - stop playback when modal is closed
        const modal = document.getElementById('listeningModal');
        if (modal) {
            modal.addEventListener('hidden.bs.modal', () => {
                this.stopPlayback();
            });
        }
    }

    /**
     * Unlock audio context for mobile devices
     */
    async unlockAudioContext() {
        if (!this.isMobile || this.audioUnlocked) {
            return true;
        }

        try {
            // Create audio context if needed
            if (!this.audioContext) {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }

            // Resume audio context (required for iOS)
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
            }

            // Create and play silent audio to unlock
            const silentBuffer = this.audioContext.createBuffer(1, 1, 22050);
            const source = this.audioContext.createBufferSource();
            source.buffer = silentBuffer;
            source.connect(this.audioContext.destination);
            source.start();

            // Also unlock existing TTSManager if available
            if (window.ttsManager && !window.ttsManager.userInteracted) {
                window.ttsManager.userInteracted = true;
            }

            this.audioUnlocked = true;
            return true;

        } catch (error) {
            console.error('Failed to unlock audio context:', error);
            return false;
        }
    }

    /**
     * Chrome iOS-specific immediate audio unlock
     */
    async unlockAudioForChromeIOS() {
        try {
            // Create Audio element during user interaction (don't play yet)
            // This "touches" the audio subsystem and unlocks it for Chrome iOS
            const touchedAudio = new Audio();
            touchedAudio.volume = 1.0;
            touchedAudio.preload = 'auto';

            // Set a minimal audio source but don't play yet
            touchedAudio.src = 'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=';

            // Just loading the audio during user interaction unlocks it for Chrome iOS
            touchedAudio.load();

            // Store for TTSManager to reuse
            if (window.ttsManager) {
                window.ttsManager.primedAudioForChromeIOS = touchedAudio;
                window.ttsManager.userInteracted = true;
            }

            this.audioUnlocked = true;
            return true;

        } catch (error) {
            console.error('Chrome iOS audio unlock failed:', error);

            // Fallback: Just set the flag anyway
            if (window.ttsManager) {
                window.ttsManager.userInteracted = true;
            }

            this.audioUnlocked = true;
            return true; // Continue anyway, might still work
        }
    }

    /**
     * Detect Chrome iOS specifically
     */
    isChromeIOS() {
        return /CriOS/i.test(navigator.userAgent) && /iPhone|iPad|iPod/i.test(navigator.userAgent);
    }

    /**
     * Start listening session for a tab
     */
    async startListening(tabName) {
        this.tabName = tabName;
        this.currentCardIndex = 0;
        this.isPlaying = false;
        this.isPaused = false;

        try {
            // Show setup view first
            this.showSetupView();

            // For mobile, show unlock prompt first
            if (this.isMobile && !this.audioUnlocked) {
                this.showMobileUnlockPrompt();
                return;
            }

            // For desktop or already unlocked mobile, show start button
            this.showDesktopStartPrompt();

        } catch (error) {
            console.error('Error starting listening mode:', error);
            this.updateStatus(`Error: ${error.message}`, false);
        }
    }

    /**
     * Show the setup view (called when modal opens)
     */
    showSetupView() {
        // Show setup view, hide progress view
        const setupView = document.getElementById('listeningSetup');
        const progressView = document.getElementById('listeningProgress');

        if (setupView) {
            setupView.style.display = 'block';
        }
        if (progressView) {
            progressView.style.display = 'none';
        }
    }

    /**
     * Enhanced mobile unlock prompt with Chrome iOS support
     */
    showMobileUnlockPrompt() {
        // Hide desktop start button, show mobile unlock
        const mobileUnlock = document.getElementById('mobileAudioUnlock');
        const desktopStart = document.getElementById('desktopAudioStart');

        if (mobileUnlock) {
            mobileUnlock.style.display = 'block';
        }
        if (desktopStart) {
            desktopStart.style.display = 'none';
        }

        // Add click handler for unlock button
        const unlockBtn = document.getElementById('unlockAudioBtn');
        if (unlockBtn) {
            // Remove any existing listeners
            unlockBtn.replaceWith(unlockBtn.cloneNode(true));
            const newUnlockBtn = document.getElementById('unlockAudioBtn');

            newUnlockBtn.addEventListener('click', async () => {
                // Show loading
                newUnlockBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Unlocking...';
                newUnlockBtn.disabled = true;

                // Chrome iOS specific immediate unlock
                if (this.isChromeIOS()) {
                    const unlocked = await this.unlockAudioForChromeIOS();

                    if (unlocked) {
                        await this.continueAfterUnlock();
                    } else {
                        newUnlockBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Chrome iOS - Try Safari';
                        newUnlockBtn.disabled = false;
                    }
                } else {
                    // Standard unlock for Safari iOS and other browsers
                    const unlocked = await this.unlockAudioContext();

                    if (unlocked) {
                        await this.continueAfterUnlock();
                    } else {
                        newUnlockBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Unlock Failed - Try Refresh';
                        newUnlockBtn.disabled = false;
                    }
                }
            }, { once: true });
        }
    }

    /**
     * Show desktop start prompt using pre-defined HTML elements
     */
    showDesktopStartPrompt() {
        // Hide mobile unlock, show desktop start
        const mobileUnlock = document.getElementById('mobileAudioUnlock');
        const desktopStart = document.getElementById('desktopAudioStart');

        if (mobileUnlock) {
            mobileUnlock.style.display = 'none';
        }
        if (desktopStart) {
            desktopStart.style.display = 'block';
        }

        // Add click handler for start button
        const startBtn = document.getElementById('startListeningBtn');
        if (startBtn) {
            // Remove any existing listeners
            startBtn.replaceWith(startBtn.cloneNode(true));
            const newStartBtn = document.getElementById('startListeningBtn');

            newStartBtn.addEventListener('click', async () => {
                // Show loading
                newStartBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Loading...';
                newStartBtn.disabled = true;

                // Continue with normal flow
                await this.continueAfterUnlock();
            }, { once: true });
        }
    }

    /**
     * Continue listening session after audio unlock (or desktop start)
     */
    async continueAfterUnlock() {
        try {
            // Switch to progress view and show loading
            this.showProgressView();
            this.updateStatus('Loading cards...', true);

            // Fetch cards from API
            const response = await fetch(`/api/cards/${encodeURIComponent(this.tabName)}`);
            const data = await response.json();

            if (!data.success) {
                throw new Error(data.error || 'Failed to fetch cards');
            }

            this.cards = data.cards;
            this.tabName = data.tab_name;
            this.sheetGid = data.sheet_gid;
            this.totalCount = data.total_count;

            console.log(`📚 Loaded ${this.totalCount} cards for listening`);

            if (this.totalCount === 0) {
                throw new Error('No cards available for listening');
            }

            // Start playback
            await this.beginPlayback();

        } catch (error) {
            console.error('Error continuing after unlock:', error);
            this.updateStatus(`Error: ${error.message}`, false);
        }
    }

    /**
     * Begin sequential playback
     */
    async beginPlayback() {
        this.isPlaying = true;
        this.isPaused = false;
        this.currentCardIndex = 0;

        // Switch to progress view
        this.showProgressView();

        console.log(`🎬 Beginning playback of ${this.totalCount} cards`);

        // Pre-populate cache for smooth infinite loops
        await this.populateAudioCache();

        // Start playing cards
        await this.playNextCard();
    }

    /**
     * Pre-populate TTSManager cache with all card audio for smooth infinite loops
     */
    async populateAudioCache() {
        if (!window.ttsManager || !window.ttsManager.isAvailable) {
            console.log('⚠️ TTS not available, skipping cache population');
            return;
        }

        console.log('🗂️ Pre-populating audio cache for infinite loop...');
        this.updateStatus('Preparing audio cache...', true);

        const spreadsheetId = window.cardContext?.spreadsheetId || null;
        let cachedCount = 0;
        let totalItems = this.cards.length * 2; // word + example per card

        try {
            // Pre-generate audio for all cards
            for (let i = 0; i < this.cards.length; i++) {
                const card = this.cards[i];

                // Check if we should continue (user might have stopped)
                if (!this.isPlaying) {
                    console.log('🛑 Cache population stopped by user');
                    return;
                }

                // Cache word and example separately using TTSManager's cache keys
                const wordCacheKey = `${card.word.trim()}_default`;
                const exampleCacheKey = `${card.example.trim()}_default`;

                // Only generate if not already cached
                if (!window.ttsManager.audioCache.has(wordCacheKey) ||
                    !window.ttsManager.audioCache.has(exampleCacheKey)) {

                    console.log(`🎵 Caching audio for card ${i + 1}: ${card.word}`);

                    // Use speakCard but don't autoplay (just cache)
                    await window.ttsManager.speakCard(
                        card.word,
                        card.example,
                        null, // voice name
                        false, // autoplay = false (just cache)
                        spreadsheetId,
                        this.sheetGid
                    );

                    cachedCount += 2; // word + example

                    // Brief delay to prevent overwhelming the API
                    await new Promise(resolve => setTimeout(resolve, 100));
                } else {
                    console.log(`✅ Audio already cached for: ${card.word}`);
                    cachedCount += 2;
                }

                // Update progress
                const progress = Math.round((cachedCount / totalItems) * 100);
                this.updateStatus(`Preparing audio cache... ${progress}%`, true);
            }

            console.log(`✅ Audio cache populated: ${cachedCount} items cached`);

        } catch (error) {
            console.error('Error populating audio cache:', error);
            // Continue anyway - we'll fall back to on-demand generation
        }
    }

    /**
     * Play the next card in sequence
     */
    async playNextCard() {
        // Check if we should continue playing
        if (!this.isPlaying || this.isPaused) {
            return;
        }

        // Check if we've reached the end of the current loop
        if (this.currentCardIndex >= this.cards.length) {
            // Infinite loop: restart from beginning
            this.loopCount++;
            this.restartLoop();
            return;
        }

        const card = this.cards[this.currentCardIndex];

        // Update progress UI
        this.updateProgress();
        this.updateStatus('Playing audio...');

        try {
            // Play the card audio using cached approach
            await this.playCardAudio(card);

            // Move to next card
            this.currentCardIndex++;

            // Brief pause between cards
            setTimeout(() => {
                if (this.isPlaying && !this.isPaused) {
                    this.playNextCard();
                }
            }, 500);

        } catch (error) {
            console.error(`Error playing card ${this.currentCardIndex + 1}:`, error);

            // Skip to next card on error
            this.currentCardIndex++;
            this.updateStatus(`Error playing card, skipping...`);

            setTimeout(() => {
                if (this.isPlaying && !this.isPaused) {
                    this.playNextCard();
                }
            }, 1000);
        }
    }

    /**
     * Restart the card loop for infinite playback
     */
    restartLoop() {
        // Reset to beginning
        this.currentCardIndex = 0;

        // Reshuffle cards for variety
        if (this.cards && this.cards.length > 0) {
            // Fisher-Yates shuffle
            for (let i = this.cards.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                [this.cards[i], this.cards[j]] = [this.cards[j], this.cards[i]];
            }
        }

        // Update UI to show new loop starting
        const loopCounter = document.getElementById('loopCounter');
        if (loopCounter) {
            loopCounter.textContent = `Loop ${this.loopCount}`;
        }

        // Continue playing if still active
        if (this.isPlaying && !this.isPaused) {
            setTimeout(() => {
                this.playNextCard();
            }, 1000); // Slightly longer pause between loops
        }
    }

    /**
     * Play audio for a single card using cached audio when possible
     */
    async playCardAudio(card) {
        return new Promise(async (resolve, reject) => {
            try {
                // Play word first (cache-first approach)
                await this.playIndividualAudio(card.word, 'word');

                // Brief delay between word and example
                await new Promise(resolve => setTimeout(resolve, 1000));

                // Play example (cache-first approach)
                await this.playIndividualAudio(card.example, 'example');

                resolve();

            } catch (error) {
                console.error(`Audio error for card: ${card.word}`, error);
                reject(error);
            }
        });
    }

    /**
     * Play individual audio (word or example) using cache-first approach
     */
    async playIndividualAudio(text, type) {
        return new Promise(async (resolve, reject) => {
            try {
                // Use TTSManager's speak method which checks cache first
                const success = await window.ttsManager.speak(text.trim());

                if (!success) {
                    throw new Error(`Failed to play ${type}: ${text}`);
                }

                // Wait for audio to complete
                if (window.ttsManager.currentAudio) {
                    const audio = window.ttsManager.currentAudio;
                    let resolved = false;

                    const resolveOnce = () => {
                        if (!resolved) {
                            resolved = true;
                            resolve();
                        }
                    };

                    // Listen for audio completion
                    audio.addEventListener('ended', resolveOnce, { once: true });

                    // Fallback timeout
                    setTimeout(() => {
                        if (!resolved) {
                            resolveOnce();
                        }
                    }, 10000); // 10 second timeout

                    // Error handling
                    audio.addEventListener('error', (e) => {
                        console.error(`Audio error for ${type}:`, e);
                        if (!resolved) {
                            resolved = true;
                            reject(new Error(`Audio playback failed for ${type}`));
                        }
                    }, { once: true });

                } else {
                    // No audio element, resolve immediately
                    setTimeout(resolve, 500);
                }

            } catch (error) {
                console.error(`Individual audio error for ${type}:`, error);
                reject(error);
            }
        });
    }

    /**
     * Simulate card playback when TTS is not available (for testing)
     */
    async simulateCardPlayback(card) {
        return new Promise(resolve => {
            // Simulate typical card duration (word + example + pauses)
            const duration = this.isMobile ? 4000 : 3000;
            setTimeout(resolve, duration);
        });
    }

    /**
     * Pause playback
     */
    pausePlayback() {
        if (!this.isPlaying) return;

        this.isPaused = true;

        // Stop current audio
        if (window.ttsManager && window.ttsManager.currentAudio) {
            window.ttsManager.currentAudio.pause();
        }

        // Update button
        const pauseResumeBtn = document.getElementById('pauseResumeBtn');
        if (pauseResumeBtn) {
            pauseResumeBtn.innerHTML = '<i class="fas fa-play"></i> <span>Resume</span>';
        }

        // Update status
        this.updateStatus('Paused');
    }

    /**
     * Resume playback
     */
    resumePlayback() {
        if (!this.isPlaying || !this.isPaused) return;

        this.isPaused = false;

        // Update button
        const pauseResumeBtn = document.getElementById('pauseResumeBtn');
        if (pauseResumeBtn) {
            pauseResumeBtn.innerHTML = '<i class="fas fa-pause"></i> <span>Pause</span>';
        }

        // Continue playing from current card
        this.playNextCard();
    }

    /**
     * Stop playback completely (called when modal is closed)
     */
    stopPlayback() {
        this.isPlaying = false;
        this.isPaused = false;

        // Stop current audio
        if (window.ttsManager) {
            window.ttsManager.stopCurrentAudio();
        }

        // Reset state
        this.currentSession = null;
        this.currentCardIndex = 0;
        this.cards = [];

        // Keep audio unlocked for potential future sessions
        // Don't reset audioUnlocked flag
    }

    /**
     * Show the progress view and hide setup view
     */
    showProgressView() {
        // Hide setup view
        const setupView = document.getElementById('listeningSetup');
        if (setupView) {
            setupView.style.display = 'none';
        }

        // Show progress view
        const progressView = document.getElementById('listeningProgress');
        if (progressView) {
            progressView.style.display = 'block';
        }

        // Update cache status
        this.updateCacheStatus();
    }

    /**
     * Update cache status display
     */
    updateCacheStatus() {
        const cacheInfo = this.getCacheInfo();
        const cacheStatusEl = document.getElementById('cacheStatus');
        const cacheHitRateEl = document.getElementById('cacheHitRate');

        if (cacheStatusEl && cacheInfo.available) {
            cacheStatusEl.textContent = `Cache: ${cacheInfo.cacheSize} items`;
        }

        if (cacheHitRateEl && cacheInfo.available) {
            cacheHitRateEl.textContent = `Hit rate: ${cacheInfo.cacheHitRate}%`;
        }
    }

    /**
     * Update status text and loading state
     */
    updateStatus(message, isLoading = false) {
        // Update status text element
        const statusTextEl = document.getElementById('statusText');
        if (statusTextEl) {
            statusTextEl.textContent = message;
        }

        // Update current card display during preparation
        if (isLoading && message.includes('cache')) {
            const currentWordEl = document.getElementById('currentWord');
            const currentExampleEl = document.getElementById('currentExample');

            if (currentWordEl) {
                currentWordEl.textContent = 'Preparing Audio...';
            }
            if (currentExampleEl) {
                currentExampleEl.textContent = 'Caching all cards for smooth playback';
            }
        }

        // Update cache status
        this.updateCacheStatus();
    }

    /**
     * Update the progress bar and card info
     */
    updateProgress() {
        const progress = Math.round(((this.currentCardIndex + 1) / this.totalCount) * 100);

        // Update progress bar
        const progressBar = document.getElementById('listeningProgressBar');
        if (progressBar) {
            progressBar.style.width = `${progress}%`;
            progressBar.setAttribute('aria-valuenow', progress.toString());
        }

        // Update progress text
        const progressText = document.getElementById('progressText');
        if (progressText) {
            progressText.textContent = `${this.currentCardIndex + 1} / ${this.totalCount} cards`;
        }

        // Update current card display
        if (this.cards && this.cards[this.currentCardIndex]) {
            const card = this.cards[this.currentCardIndex];

            const currentWordEl = document.getElementById('currentWord');
            const currentExampleEl = document.getElementById('currentExample');

            if (currentWordEl) {
                currentWordEl.textContent = card.word;
            }
            if (currentExampleEl) {
                currentExampleEl.textContent = card.example;
            }
        }

        // Update loop counter
        const loopCounter = document.getElementById('loopCounter');
        if (loopCounter) {
            loopCounter.textContent = `Loop ${this.loopCount}`;
        }

        // Update cache status
        this.updateCacheStatus();
    }

    /**
     * Get current session info for debugging
     */
    getSessionInfo() {
        return {
            tabName: this.tabName,
            totalCards: this.totalCount,
            currentIndex: this.currentCardIndex,
            isPlaying: this.isPlaying,
            isPaused: this.isPaused
        };
    }

    /**
     * Get cache statistics for debugging
     */
    getCacheInfo() {
        if (!window.ttsManager) {
            return { available: false };
        }

        const stats = window.ttsManager.getCacheStats();
        return {
            available: true,
            cacheSize: stats.size,
            memoryUsage: stats.memoryUsage,
            cardsExpected: this.totalCount * 2, // word + example per card
            cacheHitRate: this.totalCount > 0 ? Math.round((stats.size / (this.totalCount * 2)) * 100) : 0
        };
    }
}

// Global listening manager instance
window.listeningManager = new ListeningManager();

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ListeningManager;
}
