/**
 * Minimalistic TTS Manager with persistent caching
 * Phase 1: Unified Mobile Unlock Architecture
 */
class TTSManager {
    constructor() {
        this.isAvailable = true;
        this.audioCache = new Map();
        this.currentAudio = null;
        this.pendingRequests = new Map();

        // Mobile audio management - unified approach
        this.audioUnlocked = false;  // Changed from userInteracted
        this.primedAudioForChromeIOS = null;
        this.browserType = this.detectBrowser();  // Detect browser once

        console.log(`🎵 TTSManager initialized for: ${this.browserType}`);

        // Desktop browsers don't need unlock - set synchronously!
        if (this.browserType === 'desktop') {
            this.audioUnlocked = true;
            console.log('🖥️ Desktop browser - audio unlocked by default');
        }

        // Check if already unlocked in this session (synchronously)
        try {
            const storedUnlock = sessionStorage.getItem('tts_audio_unlocked');
            if (storedUnlock === 'true') {
                this.audioUnlocked = true;
                console.log('💾 Audio unlock state restored from session');
            }
        } catch (error) {
            console.warn('⚠️ Could not access sessionStorage:', error);
        }

        // Restore cache from sessionStorage
        this.restoreCache();

        // Check TTS availability (async, but not blocking)
        this.init();
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

    async init() {
        // Check TTS service availability
        try {
            const response = await fetch('/api/tts/status');
            const data = await response.json();
            this.isAvailable = data.available;
            console.log(`📡 TTS service available: ${this.isAvailable}`);
        } catch (error) {
            console.error('❌ TTS init failed:', error);
        }
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

    restoreCache() {
        try {
            const cached = sessionStorage.getItem('tts_cache');
            if (cached) {
                this.audioCache = new Map(JSON.parse(cached));
                console.log(`💾 Restored ${this.audioCache.size} cached items`);
            }
        } catch (error) {
            console.warn('⚠️ Cache restore failed:', error);
        }
    }

    saveCache() {
        try {
            sessionStorage.setItem('tts_cache', JSON.stringify([...this.audioCache]));
        } catch (error) {
            console.warn('⚠️ Cache save failed:', error);
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

    async speakCard(word, example, voice = null, autoplay = false, spreadsheetId = null, sheetGid = null) {
        // Wait for service if needed
        if (!this.isAvailable && !await this.waitForService()) {
            console.warn('⚠️ TTS service unavailable');
            return false;
        }

        // Check cache
        const wordKey = word ? this.getCacheKey(word, voice) : null;
        const exampleKey = example ? this.getCacheKey(example, voice) : null;

        const wordCached = !word || this.audioCache.has(wordKey);
        const exampleCached = !example || this.audioCache.has(exampleKey);

        if (wordCached && exampleCached) {
            console.log(`🎯 Cache hit: "${word || ''}" + "${example || ''}"`);

            // Always return audio data structure, whether from cache or API
            const audioData = {};
            if (word) audioData.word = { audio_base64: this.audioCache.get(wordKey) };
            if (example) audioData.example = { audio_base64: this.audioCache.get(exampleKey) };

            if (autoplay) {
                await this.playCardAudio(audioData);
            }

            return audioData; // Return actual audio data, not true
        }

        // Check for pending request
        const pendingKey = `${word || ''}_${example || ''}_${voice || 'default'}`;
        if (this.pendingRequests.has(pendingKey)) {
            return this.pendingRequests.get(pendingKey);
        }

        console.log(`📡 Fetching: "${word || ''}" + "${example || ''}"`);

        // Create API request
        const requestPromise = this.fetchCardAudio(word, example, voice, autoplay, spreadsheetId, sheetGid);
        this.pendingRequests.set(pendingKey, requestPromise);

        requestPromise.finally(() => this.pendingRequests.delete(pendingKey));

        return requestPromise;
    }

    async fetchCardAudio(word, example, voice, autoplay, spreadsheetId, sheetGid) {
        try {
            const body = { word, example, voice_name: voice };
            if (spreadsheetId && sheetGid !== null) {
                body.spreadsheet_id = spreadsheetId;
                body.sheet_gid = sheetGid;
            }

            const response = await fetch('/api/tts/speak-card', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            const data = await response.json();

            if (data.success && data.audio) {
                // Cache audio
                if (data.audio.word) {
                    this.audioCache.set(this.getCacheKey(word, voice), data.audio.word.audio_base64);
                }
                if (data.audio.example) {
                    this.audioCache.set(this.getCacheKey(example, voice), data.audio.example.audio_base64);
                }

                this.saveCache();

                // Play if requested
                if (autoplay) {
                    await this.playCardAudio(data.audio);
                }

                return data.audio;
            } else {
                console.error('❌ TTS API failed:', data.error);
                return false;
            }
        } catch (error) {
            console.error('💥 TTS request error:', error);
            return false;
        }
    }

    async playAudio(audioBase64) {
        try {
            // Check if audio is unlocked before attempting playback
            if (!this.audioUnlocked) {
                console.warn('⚠️ Audio not unlocked - playback may be blocked');
                // Throw NotAllowedError-like error to trigger fallback handling
                const error = new Error('Audio playback not allowed - user interaction required');
                error.name = 'NotAllowedError';
                throw error;
            }

            // Only stop current audio, not ALL audio (too aggressive)
            this.stopCurrentAudio();

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

            // Wait for audio to be ready
            await new Promise((resolve, reject) => {
                const timeout = setTimeout(() => reject(new Error('Audio load timeout')), 10000);

                audio.addEventListener('canplaythrough', () => {
                    console.log(`📻 Audio ready to play [${base64Preview}...]`);
                    clearTimeout(timeout);
                    resolve();
                }, { once: true });

                audio.addEventListener('error', () => {
                    clearTimeout(timeout);
                    reject(new Error('Load failed'));
                });

                // Only call load() if not using primed audio (it's already loaded)
                if (!this.primedAudioForChromeIOS) {
                    audio.load();
                } else {
                    // For primed audio, trigger load event quickly
                    setTimeout(() => {
                        clearTimeout(timeout);
                        resolve();
                    }, 100);
                }
            });

            console.log(`▶️ Playing audio... [${base64Preview}...]`);
            await audio.play();
            console.log(`🎵 Audio play() started, waiting for completion... [${base64Preview}...]`);

            // CRITICAL FIX: Wait for audio to actually finish playing
            return new Promise((resolve, reject) => {
                let finished = false;

                const finishAudio = () => {
                    if (!finished) {
                        finished = true;
                        console.log(`✅ Audio playback completed [${base64Preview}...]`);
                        // Only clear current audio if this is still the active one
                        if (this.currentAudio === audio) {
                            this.currentAudio = null;
                        }
                        resolve(true);
                    }
                };

                // Listen for natural completion
                audio.addEventListener('ended', finishAudio, { once: true });

                // Handle errors
                audio.addEventListener('error', (e) => {
                    console.error(`💥 Audio error during playback [${base64Preview}...]:`, e);
                    if (!finished) {
                        finished = true;
                        if (this.currentAudio === audio) {
                            this.currentAudio = null;
                        }
                        reject(new Error('Audio playback failed'));
                    }
                }, { once: true });

                // Fallback timeout (in case audio doesn't fire ended event)
                setTimeout(() => {
                    if (!finished) {
                        console.log(`⏰ Audio timeout, assuming completed [${base64Preview}...]`);
                        finishAudio();
                    }
                }, 15000); // 15 second timeout for long audio
            });

        } catch (error) {
            console.error('💥 Playback error:', error);

            if (error.name === 'NotAllowedError') {
                console.warn('🚫 Audio blocked by browser - user interaction required');
                // Don't show alert - let the UI handle it gracefully
                // The calling code should check isUnlocked() before calling playAudio()
            }

            // Return false to indicate playback failed
            return false;
        }
    }

    async playCardAudio(audioData, delay = 1000) {
        try {
            // Play word first
            if (audioData.word) {
                await this.playAudio(audioData.word.audio_base64);

                // Wait for completion + delay
                if (this.currentAudio) {
                    await new Promise(resolve => {
                        this.currentAudio.addEventListener('ended', () => {
                            setTimeout(resolve, delay);
                        });
                    });
                }
            }

            // Play example
            if (audioData.example) {
                await this.playAudio(audioData.example.audio_base64);
            }

            return true;
        } catch (error) {
            console.error('💥 Card audio error:', error);
            return false;
        }
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
