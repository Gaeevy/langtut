/**
 * Minimalistic TTS Manager with persistent caching
 * Phase 1: Unified Mobile Unlock Architecture
 */
class TTSManager {
    constructor() {
        this.enabled = false;
        this.audioUnlocked = false;
        this.browser = this.detectBrowser();
        this.primedAudioForChromeIOS = null;

        // Simplified cache (text-only keys, localStorage)
        this.audioCache = new Map();
        this.pendingRequests = new Map();

        this.init();
    }

    async init() {
        try {
            const response = await fetch('/api/tts/status');
            const data = await response.json();
            this.enabled = data.available;

            if (this.enabled) {
                this.restoreCache();
                this.checkAudioUnlock();
            }
        } catch (error) {
            console.error('TTS init failed:', error);
            this.enabled = false;
        }
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

        // Fetch both audios (with caching)
        const wordAudio = await this.fetchAudio(word, spreadsheetId, sheetGid);
        const exampleAudio = await this.fetchAudio(example, spreadsheetId, sheetGid);

        // Play if autoplay enabled
        if (autoplay && wordAudio && exampleAudio) {
            await this.playAudio(wordAudio);
            await this.playAudio(exampleAudio);
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
            console.log('✅ Play audio from cashe');
            return this.audioCache.get(cacheKey);
        }

        // Check if already pending
        if (this.pendingRequests.has(cacheKey)) {
            return this.pendingRequests.get(cacheKey);
        }

        // Build request
        const requestBody = { text };
        if (spreadsheetId) requestBody.spreadsheet_id = spreadsheetId;
        if (sheetGid) requestBody.sheet_gid = sheetGid;

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
                this.audioCache.set(cacheKey, data.audio_base64);
                this.saveCache();
                return data.audio_base64;
            } else {
                console.error('TTS failed:', data.error);
                return null;
            }
        })
        .catch(error => {
            console.error('TTS request failed:', error);
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
            return;
        }

        // Ensure audio unlocked
        if (!this.audioUnlocked) {
            await this.unlockAudio();
        }

        const audio = new Audio(`data:audio/mp3;base64,${audioBase64}`);

        return new Promise((resolve, reject) => {
            audio.onended = resolve;
            audio.onerror = reject;
            audio.play().catch(reject);
        });
    }

    checkAudioUnlock() {
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

        console.log(`🔓 Attempting to unlock audio for: ${this.browserType}`);

        try {
            let success = false;

            switch (this.browserType) {
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

    getCacheKey(text, voice = 'default') {
        return `${text}_${voice}`;
    }

    async waitForService(maxWait = 5000) {
        const start = Date.now();
        while (!this.isAvailable && Date.now() - start < maxWait) {
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        return this.isAvailable;
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

    // Enhanced speak method for individual text (restored for listening mode)
    async speak(text, voice = null) {
        if (!text || !text.trim()) {
            console.warn('No text provided for TTS');
            return false;
        }

        const trimmedText = text.trim();
        const cacheKey = this.getCacheKey(trimmedText, voice);

        // Check cache first
        if (this.audioCache.has(cacheKey)) {
            console.log(`🎯 Individual text cache hit: "${trimmedText}"`);
            return this.playAudio(this.audioCache.get(cacheKey));
        }

        // Check for pending request
        if (this.pendingRequests.has(cacheKey)) {
            return this.pendingRequests.get(cacheKey);
        }

        console.log(`📡 Fetching individual text: "${trimmedText}"`);

        // Create API request for individual text
        const requestPromise = this.fetchIndividualText(trimmedText, voice);
        this.pendingRequests.set(cacheKey, requestPromise);

        requestPromise.finally(() => this.pendingRequests.delete(cacheKey));

        return requestPromise;
    }

    async fetchIndividualText(text, voice) {
        try {
            const response = await fetch('/api/tts/speak', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: text,
                    voice_name: voice
                })
            });

            const data = await response.json();

            if (data.success && data.audio_base64) {
                // Cache the audio
                const cacheKey = this.getCacheKey(text, voice);
                this.audioCache.set(cacheKey, data.audio_base64);
                this.saveCache();

                // Play the audio
                await this.playAudio(data.audio_base64);
                return true;
            } else {
                console.error('❌ Individual text TTS failed:', data.error);
                return false;
            }
        } catch (error) {
            console.error('💥 Individual text TTS request error:', error);
            return false;
        }
    }

    clearCache() {
        this.audioCache.clear();
        this.pendingRequests.clear();
        sessionStorage.removeItem('tts_cache');
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
window.ttsManager = new TTSManager();
