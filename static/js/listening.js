/**
 * Listening Mode Manager for sequential card playback
 * Integrates with existing TTSManager for Portuguese audio
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

        // Initialize UI elements
        this.initializeUI();
    }

    /**
     * Initialize UI event handlers
     */
    initializeUI() {
        // Pause/Resume button
        const pauseBtn = document.getElementById('pause-listening-btn');
        if (pauseBtn) {
            pauseBtn.addEventListener('click', () => {
                if (this.isPaused) {
                    this.resumePlayback();
                } else {
                    this.pausePlayback();
                }
            });
        }

        // Stop button
        const stopBtn = document.getElementById('stop-listening-btn');
        if (stopBtn) {
            stopBtn.addEventListener('click', () => {
                this.stopPlayback();
            });
        }

        // Modal close handler
        const modal = document.getElementById('listeningModal');
        if (modal) {
            modal.addEventListener('hidden.bs.modal', () => {
                this.stopPlayback();
            });
        }
    }

    /**
     * Start listening session for a tab
     */
    async startListening(tabName) {
        console.log(`🎵 Starting listening mode for: ${tabName}`);

        this.tabName = tabName;
        this.currentCardIndex = 0;
        this.isPlaying = false;
        this.isPaused = false;

        try {
            // Show loading state
            this.updateStatus('Loading cards...', true);

            // Fetch cards from API
            const response = await fetch(`/api/cards/${encodeURIComponent(tabName)}`);
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
            console.error('❌ Error starting listening mode:', error);
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

        // Start playing cards
        await this.playNextCard();
    }

    /**
     * Play the next card in sequence
     */
    async playNextCard() {
        if (!this.isPlaying || this.isPaused) {
            console.log('⏸️ Playback stopped or paused');
            return;
        }

        if (this.currentCardIndex >= this.totalCount) {
            console.log('🏁 Reached end of cards');
            this.completeSession();
            return;
        }

        const card = this.cards[this.currentCardIndex];
        console.log(`🔊 Playing card ${this.currentCardIndex + 1}/${this.totalCount}: ${card.word}`);

        // Update progress UI
        this.updateProgress(card);

        try {
            // Check if TTS is available
            if (!window.ttsManager || !window.ttsManager.isAvailable) {
                console.warn('⚠️ TTS not available, simulating playback');
                await this.simulateCardPlayback(card);
            } else {
                // Use existing TTS infrastructure
                await this.playCardAudio(card);
            }

            // Move to next card
            this.currentCardIndex++;

            // Continue to next card after a brief pause
            if (this.isPlaying && !this.isPaused) {
                setTimeout(() => {
                    this.playNextCard();
                }, 500); // Brief pause between cards
            }

        } catch (error) {
            console.error(`❌ Error playing card ${this.currentCardIndex + 1}:`, error);

            // Skip to next card on error
            this.currentCardIndex++;
            setTimeout(() => {
                this.playNextCard();
            }, 1000);
        }
    }

    /**
     * Play audio for a single card using TTS
     */
    async playCardAudio(card) {
        return new Promise(async (resolve, reject) => {
            try {
                // Get spreadsheet context for caching
                const spreadsheetId = window.cardContext?.spreadsheetId || null;

                console.log(`🎵 Playing audio for: "${card.word}" -> "${card.example}"`);

                // Use TTSManager to speak the card
                const audioData = await window.ttsManager.speakCard(
                    card.word,
                    card.example,
                    null, // voice name
                    true, // autoplay = true
                    spreadsheetId,
                    this.sheetGid
                );

                if (!audioData) {
                    throw new Error('Failed to generate card audio');
                }

                // Wait for audio to complete
                // TTSManager.playCardAudio handles word -> delay -> example sequence
                // We need to wait for both to complete

                if (window.ttsManager.currentAudio) {
                    window.ttsManager.currentAudio.addEventListener('ended', () => {
                        console.log(`✅ Completed audio for: ${card.word}`);
                        resolve();
                    }, { once: true });

                    // Fallback timeout in case 'ended' event doesn't fire
                    setTimeout(() => {
                        console.log(`⏰ Audio timeout for: ${card.word}`);
                        resolve();
                    }, 15000); // 15 second timeout
                } else {
                    // No audio element, resolve immediately
                    setTimeout(resolve, 1000);
                }

            } catch (error) {
                console.error(`❌ TTS error for card: ${card.word}`, error);
                reject(error);
            }
        });
    }

    /**
     * Simulate card playback when TTS is not available (for testing)
     */
    async simulateCardPlayback(card) {
        return new Promise(resolve => {
            console.log(`🎭 Simulating audio: "${card.word}" -> "${card.example}"`);
            // Simulate typical card duration (word + example + pauses)
            setTimeout(resolve, 3000);
        });
    }

    /**
     * Pause playback
     */
    pausePlayback() {
        console.log('⏸️ Pausing listening mode');
        this.isPaused = true;

        // Stop current audio
        if (window.ttsManager) {
            window.ttsManager.stopCurrentAudio();
        }

        // Update pause button
        this.updatePauseButton(true);
    }

    /**
     * Resume playback
     */
    resumePlayback() {
        console.log('▶️ Resuming listening mode');
        this.isPaused = false;

        // Update pause button
        this.updatePauseButton(false);

        // Continue with current card
        this.playNextCard();
    }

    /**
     * Stop playback completely
     */
    stopPlayback() {
        console.log('⏹️ Stopping listening mode');
        this.isPlaying = false;
        this.isPaused = false;

        // Stop current audio
        if (window.ttsManager) {
            window.ttsManager.stopCurrentAudio();
        }

        // Close modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('listeningModal'));
        if (modal) {
            modal.hide();
        }

        // Reset state
        this.currentSession = null;
        this.currentCardIndex = 0;
        this.cards = [];
    }

    /**
     * Complete listening session
     */
    completeSession() {
        console.log('🎉 Listening session completed');
        this.isPlaying = false;

        this.updateStatus(`
            <div class="text-success">
                <i class="bi bi-check-circle"></i>
                <h6>Session Complete!</h6>
                <p class="mb-0">Listened to ${this.totalCount} cards from "${this.tabName}"</p>
            </div>
        `, false);

        // Auto-close modal after a delay
        setTimeout(() => {
            this.stopPlayback();
        }, 3000);
    }

    /**
     * Update progress UI
     */
    updateProgress(card) {
        // Update card info
        const cardInfoEl = document.getElementById('current-card-info');
        if (cardInfoEl) {
            cardInfoEl.textContent = `Playing: ${card.word} (${this.currentCardIndex + 1}/${this.totalCount})`;
        }

        // Update progress bar
        const progressBar = document.getElementById('listening-progress-bar');
        if (progressBar) {
            const percentage = Math.round(((this.currentCardIndex + 1) / this.totalCount) * 100);
            progressBar.style.width = `${percentage}%`;
            progressBar.setAttribute('aria-valuenow', percentage.toString());
        }
    }

    /**
     * Update status message
     */
    updateStatus(html, showSpinner = false) {
        const statusEl = document.getElementById('listening-status');
        if (statusEl) {
            if (showSpinner) {
                statusEl.innerHTML = `
                    <p class="mb-1">${html}</p>
                    <div class="spinner-border spinner-border-sm text-primary" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                `;
            } else {
                statusEl.innerHTML = html;
            }
        }
    }

    /**
     * Show progress view and hide status
     */
    showProgressView() {
        const statusEl = document.getElementById('listening-status');
        const progressEl = document.getElementById('listening-progress');

        if (statusEl) statusEl.style.display = 'none';
        if (progressEl) progressEl.style.display = 'block';
    }

    /**
     * Update pause button state
     */
    updatePauseButton(isPaused) {
        const pauseBtn = document.getElementById('pause-listening-btn');
        if (pauseBtn) {
            if (isPaused) {
                pauseBtn.innerHTML = '<i class="bi bi-play"></i> Resume';
            } else {
                pauseBtn.innerHTML = '<i class="bi bi-pause"></i> Pause';
            }
        }
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
}

// Global listening manager instance
window.listeningManager = new ListeningManager();

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ListeningManager;
}
