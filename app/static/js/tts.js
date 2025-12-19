/**
 * Minimalistic TTS Manager with persistent caching
 * Phase 1: Unified Mobile Unlock Architecture
 */
class TTSManager {
    static #instance = null;

    constructor() {
        if (TTSManager.#instance) {
            return TTSManager.#instance;
        }

        this.enabled = false;
        this.audioUnlocked = false;
        this.browser = this.detectBrowser();
        this.primedAudioForChromeIOS = null;
        this.currentAudio = null;

        // Simplified cache (text-only keys)
        this.audioCache = new Map();
        this.pendingRequests = new Map();

        // Сохраняем экземпляр
        TTSManager.#instance = this;

        // Desktop browsers auto-unlocked
        if (this.browser === 'desktop') {
            this.audioUnlocked = true;
            console.log('Desktop browser - audio unlocked');
        }

        // Check if already unlocked in this session
        try {
            const storedUnlock = sessionStorage.getItem('tts_audio_unlocked');
            if (storedUnlock === 'true') {
                this.audioUnlocked = true;
                console.log('Audio unlock restored from session');
            }
        } catch (error) {
            console.warn('Could not access sessionStorage:', error);
        }

        // Restore cache
        this.restoreCache();

        // Check TTS service availability (async)
        this.init();

        return this;
    }

    static getInstance() {
        if (!TTSManager.#instance) {
            TTSManager.#instance = new TTSManager();
        }
        return TTSManager.#instance;
    }

    async init() {
        try {
            const response = await fetch('/api/tts/status');
            const data = await response.json();
            this.enabled = data.available;
            console.log(`TTS service available: ${this.enabled}`);
        } catch (error) {
            console.error('TTS init failed:', error);
            this.enabled = false;
        }
    }

    cleanupForPageUnload() {
        this.saveCache();
        this.stopAllAudio();
        console.log('🧹 TTSManager cleanup for page unload');
    }

    getCacheKey(text) {
        return text.trim();
    }

    async speakCard(word, example, autoplay = false, spreadsheetId = null, sheetGid = null) {
        /**
         * Generate and play audio for word + example.
         * Calls /speak twice (once for word, once for example).
         */
        if (!this.enabled) {
            return null;
        }

        console.log(`🎯 speakCard(autoplay=${autoplay}) - word: "${word}", example: "${example}"`);

        // Fetch both audios (with caching)
        const wordAudio = await this.fetchAudio(word, spreadsheetId, sheetGid);
        const exampleAudio = await this.fetchAudio(example, spreadsheetId, sheetGid);

        // Play if autoplay enabled
        if (autoplay && wordAudio && exampleAudio) {
            console.log('▶️ Playing audio (word + example)');
            await this.playAudio(wordAudio);
            await this.playAudio(exampleAudio);
            console.log('✅ Playback complete');
        }

        return {
            word: { text: word, audio_base64: wordAudio },
            example: { text: example, audio_base64: exampleAudio }
        };
    }

    async fetchAudio(text, spreadsheetId = null, sheetGid = null) {
        /**
         * Fetch audio from /api/tts/speak.
         * Caches in localStorage by text only.
         */
        const cacheKey = this.getCacheKey(text);

        // Check cache first
        if (this.audioCache.has(cacheKey)) {
            console.log(`💾 Cache hit: "${text.substring(0, 30)}${text.length > 30 ? '...' : ''}"`);
            return this.audioCache.get(cacheKey);
        }

        // Check if already pending
        if (this.pendingRequests.has(cacheKey)) {
            console.log(`⏳ Already fetching: "${text.substring(0, 30)}${text.length > 30 ? '...' : ''}"`);
            return this.pendingRequests.get(cacheKey);
        }

        // Build request
        const requestBody = { text };
        if (spreadsheetId) requestBody.spreadsheet_id = spreadsheetId;
        if (sheetGid) requestBody.sheet_gid = sheetGid;

        console.log(`🌐 Fetching from API: "${text.substring(0, 30)}${text.length > 30 ? '...' : ''}"`);

        // Fetch from API
        const promise = fetch('/api/tts/speak', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Cache it
                console.log(`✅ Cached: "${text.substring(0, 30)}${text.length > 30 ? '...' : ''}"`);
                this.audioCache.set(cacheKey, data.audio_base64);
                this.saveCache();
                return data.audio_base64;
            } else {
                console.error('❌ TTS failed:', data.error);
                return null;
            }
        })
        .catch(error => {
            console.error('❌ TTS request failed:', error);
            return null;
        })
        .finally(() => {
            this.pendingRequests.delete(cacheKey);
        });

        this.pendingRequests.set(cacheKey, promise);
        return promise;
    }

    async playAudio(audioBase64) {
        if (!audioBase64) {
            console.warn('⚠️ playAudio called with no audio data');
            return;
        }

        // Stop previous audio if playing
        this.stopCurrentAudio();

        // CRITICAL: Do NOT attempt to unlock here - it must happen during user interaction
        // If audio is not unlocked, playback may fail on mobile
        if (!this.audioUnlocked) {
            console.warn('⚠️ Audio not unlocked - playback may fail on mobile browsers');
            console.warn('💡 Unlock audio during a user interaction (click/touch) before calling playAudio()');
        }

        // Log base64 preview for debugging
        const base64Preview = audioBase64.substring(0, 10);
        console.log(`🔊 Starting audio playback... [${base64Preview}...]`);

        // For Chrome iOS: Use primed Audio element if available
        let audio;
        if (this.primedAudioForChromeIOS) {
            console.log('📱 Using primed Chrome iOS audio element');
            audio = this.primedAudioForChromeIOS;

            // Make sure primed audio is stopped before reusing
            if (!audio.paused) {
                audio.pause();
                audio.currentTime = 0;
            }

            // Remove any existing event listeners to prevent conflicts
            audio.onended = null;
            audio.onerror = null;
            audio.oncanplaythrough = null;

            // Reuse the primed element but update its source
            audio.src = `data:audio/mp3;base64,${audioBase64}`;
        } else {
            console.log('🖥️ Creating new audio element');
            // Create new audio element for other browsers
            audio = new Audio(`data:audio/mp3;base64,${audioBase64}`);
        }

        this.currentAudio = audio;

        return new Promise((resolve, reject) => {
            audio.onended = () => {
                console.log('✅ Audio playback ended');
                this.currentAudio = null;
                resolve();
            };
            audio.onerror = (error) => {
                console.error('❌ Audio playback error:', error);
                this.currentAudio = null;
                reject(error);
            };
            audio.play().catch(reject);
        });
    }

    restoreCache() {
        // Load from localStorage
        const cached = localStorage.getItem('tts_cache');
        if (cached) {
            try {
                this.audioCache = new Map(JSON.parse(cached));
            } catch (e) {
                console.warn('Failed to restore TTS cache:', e);
                this.audioCache = new Map();
            }
        }
    }

    saveCache() {
        // Save to localStorage
        try {
            localStorage.setItem('tts_cache', JSON.stringify([...this.audioCache]));
        } catch (e) {
            console.warn('⚠️ Failed to save TTS cache:', e);
        }
    }

    /**
     * Detect browser type for audio unlock strategy
     * @returns {string} Browser type identifier
     */
    detectBrowser() {
        const ua = navigator.userAgent;

        // Chrome iOS (most restrictive - needs special Touch Strategy)
        if (/CriOS/i.test(ua) && /iPhone|iPad|iPod/i.test(ua)) {
            return 'chrome-ios';
        }

        // Safari iOS
        if (/Safari/i.test(ua) && !/CriOS/i.test(ua) && /iPhone|iPad|iPod/i.test(ua)) {
            return 'safari-ios';
        }

        // Android browsers
        if (/Android/i.test(ua)) {
            return /Chrome/i.test(ua) ? 'android-chrome' : 'android-other';
        }

        // Desktop browsers (no unlock needed)
        return 'desktop';
    }

    /**
     * Check if audio has been unlocked for playback
     * @returns {boolean} True if audio can be played
     */
    isUnlocked() {
        return this.audioUnlocked;
    }

    isEnabled() {
        return this.enabled;
    }

    /**
     * Unlock audio for mobile browsers
     * MUST be called during a user gesture (click, touch, etc.)
     * @returns {Promise<boolean>} True if unlock successful
     */
    async unlockAudio() {
        if (this.audioUnlocked) {
            console.log('✅ Audio already unlocked');
            return true;
        }

        console.log(`🔓 Attempting to unlock audio for: ${this.browser}`);

        try {
            let success = false;

            switch (this.browser) {
                case 'chrome-ios':
                    success = await this.unlockChromeIOS();
                    break;

                case 'safari-ios':
                case 'android-chrome':
                case 'android-other':
                    success = await this.unlockMobile();
                    break;

                case 'desktop':
                    success = true;  // Already unlocked
                    break;

                default:
                    // Fallback to mobile unlock
                    success = await this.unlockMobile();
                    break;
            }

            if (success) {
                this.audioUnlocked = true;
                // Persist unlock state in session
                try {
                    sessionStorage.setItem('tts_audio_unlocked', 'true');
                } catch (error) {
                    console.warn('⚠️ Could not save unlock state:', error);
                }
                console.log('✅ Audio unlocked successfully');
            }

            return success;

        } catch (error) {
            console.error('💥 Audio unlock failed:', error);
            return false;
        }
    }

    /**
     * Chrome iOS-specific "Touch Strategy" unlock
     * Creates and loads an Audio element during user interaction
     * @returns {Promise<boolean>} True if unlock successful
     */
    async unlockChromeIOS() {
        console.log('📱 Using Chrome iOS Touch Strategy');

        try {
            // Create Audio element during user interaction (don't play yet)
            // This "touches" the audio subsystem and unlocks it for Chrome iOS
            const touchedAudio = new Audio();
            touchedAudio.volume = 1.0;
            touchedAudio.preload = 'auto';

            // Set a minimal WAV audio source
            touchedAudio.src = 'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=';

            // Just loading the audio during user interaction unlocks it for Chrome iOS
            touchedAudio.load();

            // Store for reuse throughout the session
            this.primedAudioForChromeIOS = touchedAudio;

            console.log('✅ Chrome iOS audio element primed and ready');
            return true;

        } catch (error) {
            console.error('💥 Chrome iOS unlock failed:', error);
            // Don't fail completely - might still work
            return true;
        }
    }

    /**
     * Standard mobile unlock using AudioContext
     * Works for Safari iOS, Android Chrome, and other mobile browsers
     * @returns {Promise<boolean>} True if unlock successful
     */
    async unlockMobile() {
        console.log('📱 Using standard mobile AudioContext unlock');

        try {
            // Create audio context if needed
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            if (!AudioContextClass) {
                console.warn('⚠️ AudioContext not supported');
                return true;  // Proceed anyway
            }

            const audioContext = new AudioContextClass();

            // Resume audio context (required for iOS)
            if (audioContext.state === 'suspended') {
                await audioContext.resume();
                console.log('🔊 AudioContext resumed');
            }

            // Create and play silent audio to unlock
            const silentBuffer = audioContext.createBuffer(1, 1, 22050);
            const source = audioContext.createBufferSource();
            source.buffer = silentBuffer;
            source.connect(audioContext.destination);
            source.start();

            console.log('✅ Mobile audio unlocked via AudioContext');
            return true;

        } catch (error) {
            console.error('💥 Mobile unlock failed:', error);
            // Don't fail completely - might still work
            return true;
        }
    }

    async waitForService(maxWait = 5000) {
        const start = Date.now();
        while (!this.enabled && Date.now() - start < maxWait) {
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        return this.enabled;
    }

    stopCurrentAudio() {
        if (this.currentAudio) {
            console.log('⏹️ Stopping current audio');
            try {
                this.currentAudio.pause();
                this.currentAudio.currentTime = 0;
                // Clear event listeners to prevent ghost callbacks
                this.currentAudio.onended = null;
                this.currentAudio.onerror = null;
                this.currentAudio = null;
            } catch (error) {
                console.warn('⚠️ Error stopping current audio:', error);
            }
        }
    }

    /**
     * Stop ALL possible audio sources - comprehensive cleanup
     */
    stopAllAudio() {
        console.log('🔇 Stopping ALL audio sources (comprehensive cleanup)...');

        // Stop current audio
        this.stopCurrentAudio();

        // Stop primed audio element if it exists
        if (this.primedAudioForChromeIOS) {
            try {
                console.log('🔇 Stopping primed Chrome iOS audio');
                this.primedAudioForChromeIOS.pause();
                this.primedAudioForChromeIOS.currentTime = 0;
                // Clear event listeners but don't destroy the element (keep it primed)
                this.primedAudioForChromeIOS.onended = null;
                this.primedAudioForChromeIOS.onerror = null;
                this.primedAudioForChromeIOS.oncanplaythrough = null;
            } catch (error) {
                console.warn('⚠️ Error stopping primed audio:', error);
            }
        }

        // Stop any other audio elements that might be playing
        try {
            const allAudioElements = document.querySelectorAll('audio');
            allAudioElements.forEach(audio => {
                if (!audio.paused) {
                    console.log('🔇 Stopping orphaned audio element');
                    audio.pause();
                    audio.currentTime = 0;
                }
            });
        } catch (error) {
            console.warn('⚠️ Error stopping orphaned audio elements:', error);
        }
    }

    /**
     * Reset audio system completely (for session switches)
     */
    resetAudioSystem() {
        console.log('🔄 Resetting audio system for session switch...');

        // Stop all audio
        this.stopAllAudio();

        // Clear all pending requests
        console.log('🧹 Clearing pending requests');
        this.pendingRequests.clear();

        // Don't clear the cache or primed audio - those can be reused
        // Just ensure clean audio state
    }

    clearCache() {
        this.audioCache.clear();
        this.pendingRequests.clear();
        localStorage.removeItem('tts_cache');
        console.log('🗑️ Cache cleared');
    }

    getCacheStats() {
        const size = this.audioCache.size;
        let memoryKB = 0;
        for (const [key, value] of this.audioCache) {
            memoryKB += (key.length * 2 + value.length * 0.75) / 1024;
        }

        const stats = {
            size,
            memoryKB: Math.round(memoryKB),
            pending: this.pendingRequests.size
        };

        console.log(`📊 Cache: ${stats.size} items (${stats.memoryKB}KB), ${stats.pending} pending`);
        return stats;
    }
}

// Global instance
window.ttsManager = TTSManager.getInstance();
