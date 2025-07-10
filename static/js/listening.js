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

        // Promise chain isolation - prevent ghost operations from old sessions
        this.operationToken = 0;
        this.currentOperationToken = 0;

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
            // Remove any existing listeners first
            modal.removeEventListener('hidden.bs.modal', this.stopPlayback);

            // Add the stop playback handler
            modal.addEventListener('hidden.bs.modal', () => {
                console.log('📝 Modal closed, stopping playback');
                this.stopPlayback();
            });

            // Also handle modal show event to reset state
            modal.addEventListener('show.bs.modal', () => {
                console.log('📝 Modal opening, preparing clean state');
                // Don't reset session here as startListening will handle it
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
        console.log(`🎵 Starting listening session for: ${tabName}`);

        // First, completely reset any existing session
        this.resetSession();

        // Small delay to ensure audio cleanup completes before starting new session
        await new Promise(resolve => setTimeout(resolve, 200));

        // Initialize new session state
        this.tabName = tabName;
        this.currentCardIndex = 0;
        this.isPlaying = false;
        this.isPaused = false;
        this.loopCount = 1;
        this.cards = [];
        this.sheetGid = null;
        this.totalCount = 0;
        this.currentSession = tabName; // Track current session

        try {
            // Reset UI to setup view
            this.showSetupView();
            this.resetUIElements();

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
     * Reset all session state and cleanup
     */
    resetSession() {
        console.log('🧹 Resetting session state...');

        // Stop any current playback immediately
        this.isPlaying = false;
        this.isPaused = false;

        // CRITICAL: Generate new operation token to invalidate all previous Promise chains
        this.operationToken++;
        this.currentOperationToken = this.operationToken;
        console.log(`🔑 New operation token: ${this.currentOperationToken}`);

        // CRITICAL: Use comprehensive audio cleanup to stop ALL audio sources
        if (window.ttsManager) {
            window.ttsManager.resetAudioSystem();
        }

        // Reset all session variables
        this.currentSession = null;
        this.currentCardIndex = 0;
        this.cards = [];
        this.tabName = '';
        this.sheetGid = null;
        this.totalCount = 0;
        this.loopCount = 1;

        // Reset UI elements
        this.resetUIElements();
    }

    /**
     * Reset all UI elements to their initial state
     */
    resetUIElements() {
        // Reset status
        this.updateStatus('Ready to listen', false);

        // Reset progress bar
        const progressBar = document.getElementById('listeningProgressBar');
        if (progressBar) {
            progressBar.style.width = '0%';
            progressBar.setAttribute('aria-valuenow', '0');
        }

        // Reset progress text
        const progressText = document.getElementById('progressText');
        if (progressText) {
            progressText.textContent = '0 / 0 cards';
        }

        // Reset current card display
        const currentWordEl = document.getElementById('currentWord');
        const currentExampleEl = document.getElementById('currentExample');
        if (currentWordEl) {
            currentWordEl.textContent = 'Ready to start...';
        }
        if (currentExampleEl) {
            currentExampleEl.textContent = 'Press start to begin listening session';
        }

        // Reset loop counter
        const loopCounter = document.getElementById('loopCounter');
        if (loopCounter) {
            loopCounter.textContent = 'Loop 1';
        }

        // Reset pause/resume button
        const pauseResumeBtn = document.getElementById('pauseResumeBtn');
        if (pauseResumeBtn) {
            pauseResumeBtn.innerHTML = '<i class="fas fa-pause"></i> <span>Pause</span>';
            pauseResumeBtn.disabled = false;
        }

        // Reset unlock button state
        const unlockBtn = document.getElementById('unlockAudioBtn');
        if (unlockBtn) {
            unlockBtn.innerHTML = '<i class="fas fa-volume-up"></i> Start Listening Session';
            unlockBtn.disabled = false;
        }

        // Reset start button state
        const startBtn = document.getElementById('startListeningBtn');
        if (startBtn) {
            startBtn.innerHTML = '<i class="fas fa-play"></i> Start Listening';
            startBtn.disabled = false;
        }

        // Update cache status
        this.updateCacheStatus();
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

        // Add click handler for unlock button - ensure clean state
        const unlockBtn = document.getElementById('unlockAudioBtn');
        if (unlockBtn) {
            // Remove any existing listeners and reset button
            unlockBtn.replaceWith(unlockBtn.cloneNode(true));
            const newUnlockBtn = document.getElementById('unlockAudioBtn');

            // Reset button state
            newUnlockBtn.innerHTML = '<i class="fas fa-volume-up"></i> Start Listening Session';
            newUnlockBtn.disabled = false;

            newUnlockBtn.addEventListener('click', async () => {
                // Show loading
                newUnlockBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Unlocking...';
                newUnlockBtn.disabled = true;

                try {
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
                } catch (error) {
                    console.error('Error during unlock:', error);
                    newUnlockBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Error - Try Again';
                    newUnlockBtn.disabled = false;
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

        // Add click handler for start button - ensure clean state
        const startBtn = document.getElementById('startListeningBtn');
        if (startBtn) {
            // Remove any existing listeners and reset button
            startBtn.replaceWith(startBtn.cloneNode(true));
            const newStartBtn = document.getElementById('startListeningBtn');

            // Reset button state
            newStartBtn.innerHTML = '<i class="fas fa-play"></i> Start Listening';
            newStartBtn.disabled = false;

            newStartBtn.addEventListener('click', async () => {
                // Show loading
                newStartBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Loading...';
                newStartBtn.disabled = true;

                try {
                    // Continue with normal flow
                    await this.continueAfterUnlock();
                } catch (error) {
                    console.error('Error during start:', error);
                    newStartBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Error - Try Again';
                    newStartBtn.disabled = false;
                }
            }, { once: true });
        }
    }

    /**
     * Continue listening session after audio unlock (or desktop start)
     */
    async continueAfterUnlock() {
        try {
            // Verify we're still in the right session (user might have switched tabs)
            if (!this.tabName || !this.currentSession) {
                throw new Error('Session was reset, please try again');
            }

            // Switch to progress view and show loading
            this.showProgressView();
            this.updateStatus('Loading cards...', true);

            // Fetch cards from API
            console.log(`📡 Fetching cards for: ${this.tabName}`);
            const response = await fetch(`/api/cards/${encodeURIComponent(this.tabName)}`);
            const data = await response.json();

            if (!data.success) {
                throw new Error(data.error || 'Failed to fetch cards');
            }

            // Verify we're still in the same session
            if (this.currentSession !== this.tabName) {
                console.log('⚠️ Session changed during card loading, aborting');
                return;
            }

            this.cards = data.cards;
            this.tabName = data.tab_name;
            this.sheetGid = data.sheet_gid;
            this.totalCount = data.total_count;

            console.log(`📚 Loaded ${this.totalCount} cards for listening: ${this.tabName}`);

            if (this.totalCount === 0) {
                throw new Error('No cards available for listening');
            }

            // Start playback
            await this.beginPlayback();

        } catch (error) {
            console.error('Error continuing after unlock:', error);
            this.updateStatus(`Error: ${error.message}`, false);

            // Reset to setup view on error
            setTimeout(() => {
                if (this.currentSession === this.tabName) {
                    this.showSetupView();
                    this.resetUIElements();
                }
            }, 3000);
        }
    }

    /**
     * Begin sequential playback
     */
    async beginPlayback() {
        // Verify session hasn't changed
        if (!this.currentSession || this.currentSession !== this.tabName) {
            console.log('⚠️ Session changed, aborting playback');
            return;
        }

        this.isPlaying = true;
        this.isPaused = false;
        this.currentCardIndex = 0;

        // Switch to progress view
        this.showProgressView();

        console.log(`🎬 Beginning playback of ${this.totalCount} cards for: ${this.tabName}`);

        // Skip pre-caching - use just-in-time loading instead
        this.updateStatus('Starting playback...', false);

        // Start playing cards immediately
        await this.playNextCard();
    }

    /**
     * Play the next card in sequence
     */
    async playNextCard() {
        // Capture current token at the start of this operation
        const operationToken = this.currentOperationToken;

        // Check if we should continue playing and session is still active
        if (!this.isPlaying || this.isPaused || this.currentSession !== this.tabName) {
            console.log('⚠️ Playback stopped or session changed');
            return;
        }

        // Check if operation token is still valid (session hasn't changed)
        if (operationToken !== this.currentOperationToken) {
            console.log(`🚫 Operation token mismatch: ${operationToken} vs ${this.currentOperationToken}, ignoring`);
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

        // Update progress UI (only if token still valid)
        if (operationToken === this.currentOperationToken) {
            this.updateProgress();
            this.updateStatus('Loading card audio...');
        }

        try {
            console.log(`🎵 Starting card ${this.currentCardIndex + 1} with token ${operationToken}`);

            // Load and play current card audio on-demand
            await this.playCardAudioJustInTime(card, operationToken);

            // Verify token is still valid after playing
            if (operationToken !== this.currentOperationToken) {
                console.log(`🚫 Token expired after card playback: ${operationToken} vs ${this.currentOperationToken}`);
                return;
            }

            // Verify session is still active after playing
            if (!this.isPlaying || this.isPaused || this.currentSession !== this.tabName) {
                console.log('⚠️ Session changed during card playback');
                return;
            }

            // Move to next card
            this.currentCardIndex++;

            // Background load next card while we pause between cards
            this.prefetchNextCard(operationToken);

            // Brief pause between cards
            setTimeout(() => {
                // Double-check token before continuing
                if (operationToken === this.currentOperationToken &&
                    this.isPlaying && !this.isPaused && this.currentSession === this.tabName) {
                    this.playNextCard();
                } else {
                    console.log(`🚫 Skipping next card due to token/session change: ${operationToken} vs ${this.currentOperationToken}`);
                }
            }, 500);

        } catch (error) {
            // Only log error if token is still valid (not a cancelled operation)
            if (operationToken === this.currentOperationToken) {
                console.error(`Error playing card ${this.currentCardIndex + 1}:`, error);

                // Skip to next card on error
                this.currentCardIndex++;
                this.updateStatus(`Error playing card, skipping...`);

                setTimeout(() => {
                    if (operationToken === this.currentOperationToken &&
                        this.isPlaying && !this.isPaused && this.currentSession === this.tabName) {
                        this.playNextCard();
                    }
                }, 1000);
            } else {
                console.log(`🚫 Ignoring error from cancelled operation: ${operationToken} vs ${this.currentOperationToken}`);
            }
        }
    }

    /**
     * Load and play card audio on-demand (just-in-time)
     */
    async playCardAudioJustInTime(card, operationToken) {
        const currentSession = this.currentSession;

        console.log(`🎵 Loading audio for card: "${card.word}" (token: ${operationToken})`);

        // Use TTSManager's speakCard with autoplay to load and play immediately
        const spreadsheetId = window.cardContext?.spreadsheetId || null;

        try {
            // Validate token before starting
            if (operationToken !== this.currentOperationToken) {
                console.log(`🚫 Token expired before loading: ${operationToken} vs ${this.currentOperationToken}`);
                return;
            }

            // Load both word and example audio, then play them in sequence
            const audioData = await window.ttsManager.speakCard(
                card.word,
                card.example,
                null, // voice name
                false, // autoplay = false (we'll control playback manually)
                spreadsheetId,
                this.sheetGid
            );

            // Check if token/session changed during loading
            if (operationToken !== this.currentOperationToken) {
                console.log(`🚫 Token expired during loading: ${operationToken} vs ${this.currentOperationToken}`);
                return;
            }

            if (!this.isPlaying || this.currentSession !== currentSession) {
                console.log('⚠️ Session changed during card loading, aborting playback');
                return;
            }

            if (!audioData) {
                throw new Error('Failed to load card audio');
            }

            this.updateStatus('Playing audio...');

            // Play word first
            console.log(`🎤 Playing word: "${card.word}" (token: ${operationToken})`);
            const wordBase64Preview = audioData.word.audio_base64.substring(0, 10);
            console.log(`🎵 Word audio: [${wordBase64Preview}...]`);
            await window.ttsManager.playAudio(audioData.word.audio_base64);

            // Check token/session again after word
            if (operationToken !== this.currentOperationToken) {
                console.log(`🚫 Token expired after word: ${operationToken} vs ${this.currentOperationToken}`);
                return;
            }

            if (!this.isPlaying || this.currentSession !== currentSession) {
                console.log('⚠️ Session changed during word playback');
                return;
            }

            // Brief delay between word and example
            await new Promise(resolve => setTimeout(resolve, 1000));

            // Check token/session again before example
            if (operationToken !== this.currentOperationToken) {
                console.log(`🚫 Token expired before example: ${operationToken} vs ${this.currentOperationToken}`);
                return;
            }

            if (!this.isPlaying || this.currentSession !== currentSession) {
                console.log('⚠️ Session changed before example playback');
                return;
            }

            // Play example
            console.log(`🎤 Playing example: "${card.example}" (token: ${operationToken})`);
            const exampleBase64Preview = audioData.example.audio_base64.substring(0, 10);
            console.log(`🎵 Example audio: [${exampleBase64Preview}...]`);
            await window.ttsManager.playAudio(audioData.example.audio_base64);

            // Final token check
            if (operationToken === this.currentOperationToken) {
                console.log(`✅ Completed card: "${card.word}" (token: ${operationToken})`);
            } else {
                console.log(`🚫 Card completed but token expired: "${card.word}" (${operationToken} vs ${this.currentOperationToken})`);
            }

        } catch (error) {
            // Only log error if token is still valid
            if (operationToken === this.currentOperationToken) {
                console.error(`💥 Error loading/playing card: ${card.word}`, error);
                throw error;
            } else {
                console.log(`🚫 Ignoring error from cancelled card operation: ${card.word} (${operationToken} vs ${this.currentOperationToken})`);
            }
        }
    }

    /**
     * Background prefetch next card to cache (non-blocking)
     */
    async prefetchNextCard(operationToken) {
        // Don't prefetch if we're at the end of cards or session changed
        if (!this.isPlaying || this.currentSession !== this.tabName) {
            return;
        }

        // Validate token before starting background operation
        if (operationToken !== this.currentOperationToken) {
            console.log(`🚫 Skipping prefetch due to token mismatch: ${operationToken} vs ${this.currentOperationToken}`);
            return;
        }

        let nextIndex = this.currentCardIndex;
        let nextCard = null;

        // Determine next card (could be next in sequence or first card of next loop)
        if (nextIndex < this.cards.length) {
            nextCard = this.cards[nextIndex];
        } else if (this.cards.length > 0) {
            // Next loop - prefetch first card
            nextCard = this.cards[0];
        }

        if (!nextCard) {
            return;
        }

        // Background prefetch (don't await - let it happen in background)
        const spreadsheetId = window.cardContext?.spreadsheetId || null;

        console.log(`🔄 Background prefetching: "${nextCard.word}" (token: ${operationToken})`);

        // Fire and forget - don't await, but validate token in completion handler
        window.ttsManager.speakCard(
            nextCard.word,
            nextCard.example,
            null, // voice name
            false, // autoplay = false (just cache)
            spreadsheetId,
            this.sheetGid
        ).then(() => {
            // Only log success if token is still valid
            if (operationToken === this.currentOperationToken) {
                console.log(`✅ Background prefetch completed: "${nextCard.word}" (token: ${operationToken})`);
            } else {
                console.log(`🚫 Background prefetch completed but token expired: "${nextCard.word}" (${operationToken} vs ${this.currentOperationToken})`);
            }
        }).catch(error => {
            // Only log error if token is still valid
            if (operationToken === this.currentOperationToken) {
                console.warn(`⚠️ Background prefetch failed for "${nextCard.word}":`, error);
            } else {
                console.log(`🚫 Ignoring prefetch error from cancelled operation: "${nextCard.word}" (${operationToken} vs ${this.currentOperationToken})`);
            }
        });
    }

    /**
     * Restart the card loop for infinite playback
     */
    restartLoop() {
        // Capture current token
        const operationToken = this.currentOperationToken;

        // Verify session is still active
        if (!this.isPlaying || this.currentSession !== this.tabName) {
            console.log('⚠️ Loop restart cancelled - session changed or stopped');
            return;
        }

        // Verify token is still valid
        if (operationToken !== this.currentOperationToken) {
            console.log(`🚫 Loop restart cancelled - token expired: ${operationToken} vs ${this.currentOperationToken}`);
            return;
        }

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

        console.log(`🔄 Starting loop ${this.loopCount} for session: ${this.currentSession} (token: ${operationToken})`);

        // Continue playing if still active
        if (this.isPlaying && !this.isPaused && this.currentSession === this.tabName) {
            setTimeout(() => {
                // Double-check token and session before continuing
                if (operationToken === this.currentOperationToken &&
                    this.isPlaying && !this.isPaused && this.currentSession === this.tabName) {
                    this.playNextCard();
                } else {
                    console.log(`🚫 Loop restart cancelled during timeout - token/session changed: ${operationToken} vs ${this.currentOperationToken}`);
                }
            }, 1000); // Slightly longer pause between loops
        }
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

        // Just stop current audio, not all audio during pause
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
        console.log('🛑 Stopping playback and cleaning up session');

        this.isPlaying = false;
        this.isPaused = false;

        // CRITICAL: Use comprehensive audio cleanup to stop ALL audio sources
        if (window.ttsManager) {
            window.ttsManager.resetAudioSystem();
        }

        // Reset all session state
        this.currentSession = null;
        this.currentCardIndex = 0;
        this.cards = [];
        this.tabName = '';
        this.sheetGid = null;
        this.totalCount = 0;
        this.loopCount = 1;

        // Reset UI elements
        this.resetUIElements();

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
            currentSession: this.currentSession,
            tabName: this.tabName,
            totalCards: this.totalCount,
            currentIndex: this.currentCardIndex,
            isPlaying: this.isPlaying,
            isPaused: this.isPaused,
            loopCount: this.loopCount,
            audioUnlocked: this.audioUnlocked,
            cardsLoaded: this.cards.length > 0
        };
    }

    /**
     * Get cache info for debugging
     */
    getCacheInfo() {
        if (!window.ttsManager) {
            return { available: false, reason: 'TTS Manager not available' };
        }

        const stats = window.ttsManager.getCacheStats();
        return {
            available: true,
            cacheSize: stats.size,
            cacheMemoryKB: stats.memoryKB,
            pendingRequests: stats.pending,
            cacheHitRate: stats.size > 0 ? Math.round((stats.size / (stats.size + stats.pending)) * 100) : 0
        };
    }

    /**
     * Debug method to log current state
     */
    logCurrentState() {
        const sessionInfo = this.getSessionInfo();
        const cacheInfo = this.getCacheInfo();

        // Add audio state information
        const audioInfo = {
            hasCurrentAudio: window.ttsManager?.currentAudio !== null,
            currentAudioSrc: window.ttsManager?.currentAudio?.src || 'none',
            hasPrimedAudio: window.ttsManager?.primedAudioForChromeIOS !== null,
            primedAudioPaused: window.ttsManager?.primedAudioForChromeIOS?.paused ?? 'N/A',
            totalAudioElements: document.querySelectorAll('audio').length,
            playingAudioElements: Array.from(document.querySelectorAll('audio')).filter(a => !a.paused).length
        };

        console.log('🔍 Listening Manager State:');
        console.log('  Session:', sessionInfo);
        console.log('  Cache:', cacheInfo);
        console.log('  Audio:', audioInfo);

        return { session: sessionInfo, cache: cacheInfo, audio: audioInfo };
    }
}

// Global listening manager instance with enhanced logging
console.log('🎵 Initializing Listening Manager...');
window.listeningManager = new ListeningManager();

// Debug helper
window.debugListening = () => {
    return window.listeningManager.logCurrentState();
};

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ListeningManager;
}
