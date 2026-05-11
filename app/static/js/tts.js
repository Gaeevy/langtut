/**
 * Minimalistic TTS Manager with persistent caching
 * Phase 1: Unified Mobile Unlock Architecture
 */
/** Client TTS blob cache: trimmed text only (tradeoff: rare stale clip if voice/language changes). */
const TTS_CACHE_STORAGE_KEY = "tts_cache";

class TTSManager {
    static #instance = null;

    constructor() {
        if (TTSManager.#instance) {
            return TTSManager.#instance;
        }

        this.enabled = false;
        this.audioUnlocked = false;
        this.browser = this.detectBrowser();
        /** HTMLAudioElement created during user gesture; reused by swapping src (iOS Safari + Chrome iOS). */
        this.primedAudioForChromeIOS = null;
        this.currentAudio = null;

        this._statusReady = false;

        this.audioCache = new Map();
        this.pendingRequests = new Map();

        TTSManager.#instance = this;

        if (this.browser === "desktop") {
            this.audioUnlocked = true;
            console.log("Desktop browser - audio unlocked");
        }

        try {
            const storedUnlock = sessionStorage.getItem("tts_audio_unlocked");
            if (storedUnlock === "true") {
                this.audioUnlocked = true;
                console.log("Audio unlock restored from session");
            }
        } catch (error) {
            console.warn("Could not access sessionStorage:", error);
        }

        this.restoreCache();

        this.initPromise = this.init();

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
            const response = await fetch("/api/tts/status");
            const data = await response.json();
            this.enabled = data.available;
            console.log(`TTS service available: ${this.enabled}`);
        } catch (error) {
            console.error("TTS init failed:", error);
            this.enabled = false;
        } finally {
            this._statusReady = true;
        }
    }

    cleanupForPageUnload() {
        this.saveCache();
        this.stopAllAudio();
        console.log("🧹 TTSManager cleanup for page unload");
    }

    /**
     * Cache key for a phrase (text only; see module comment on tradeoffs).
     * @param {string} text
     * @returns {string}
     */
    getCacheKey(text) {
        return text.trim();
    }

    /**
     * Call during a user gesture before playback on mobile (alias for unlockAudio).
     * @returns {Promise<boolean>}
     */
    async ensureUnlockedFromGesture() {
        return this.unlockAudio();
    }

    /**
     * Fetch audio for a single line of text; optionally play (e.g. debug / test pages).
     * @param {string} text
     * @param {boolean} autoplay
     * @param {string|null} spreadsheetId
     * @param {string|null} sheetGid
     * @returns {Promise<string|null>}
     */
    async speak(text, autoplay = false, spreadsheetId = null, sheetGid = null) {
        if (!this.enabled || !text || !String(text).trim()) {
            return null;
        }
        const trimmed = String(text).trim();
        const audio = await this.fetchAudio(trimmed, spreadsheetId, sheetGid);
        if (autoplay && audio) {
            await this.playAudio(audio);
        }
        return audio;
    }

    async speakCard(word, example, autoplay = false, spreadsheetId = null, sheetGid = null) {
        /**
         * Generate and play audio for word + example.
         * Calls /speak twice when example is present.
         */
        if (!this.enabled) {
            return null;
        }

        const wordTrim = word ? String(word).trim() : "";
        if (!wordTrim) {
            return null;
        }

        console.log(
            `🎯 speakCard(autoplay=${autoplay}) - word: "${wordTrim}", example: "${example ?? ""}"`
        );

        const wordAudio = await this.fetchAudio(wordTrim, spreadsheetId, sheetGid);
        const exampleTrim = example && String(example).trim() ? String(example).trim() : "";
        const exampleAudio = exampleTrim
            ? await this.fetchAudio(exampleTrim, spreadsheetId, sheetGid)
            : null;

        if (autoplay && wordAudio) {
            console.log("▶️ Playing audio (word + example if present)");
            await this.playAudio(wordAudio);
            if (exampleAudio) {
                await this.playAudio(exampleAudio);
            }
            console.log("✅ Playback complete");
        }

        return {
            word: { text: wordTrim, audio_base64: wordAudio },
            example: exampleTrim
                ? { text: exampleTrim, audio_base64: exampleAudio }
                : null,
        };
    }

    async fetchAudio(text, spreadsheetId = null, sheetGid = null) {
        /**
         * Fetch audio from /api/tts/speak.
         * Caches in localStorage by voice-aware key when prefix is known.
         */
        const cacheKey = this.getCacheKey(text);

        if (this.audioCache.has(cacheKey)) {
            console.log(`💾 Cache hit: "${text.substring(0, 30)}${text.length > 30 ? "..." : ""}"`);
            return this.audioCache.get(cacheKey);
        }

        if (this.pendingRequests.has(cacheKey)) {
            console.log(`⏳ Already fetching: "${text.substring(0, 30)}${text.length > 30 ? "..." : ""}"`);
            return this.pendingRequests.get(cacheKey);
        }

        const requestBody = { text };
        if (spreadsheetId) requestBody.spreadsheet_id = spreadsheetId;
        if (sheetGid) requestBody.sheet_gid = sheetGid;

        console.log(`🌐 Fetching from API: "${text.substring(0, 30)}${text.length > 30 ? "..." : ""}"`);

        const promise = fetch("/api/tts/speak", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(requestBody),
        })
            .then((response) => response.json())
            .then((data) => {
                if (data.success) {
                    console.log(`✅ Cached: "${text.substring(0, 30)}${text.length > 30 ? "..." : ""}"`);
                    this.audioCache.set(cacheKey, data.audio_base64);
                    this.saveCache();
                    return data.audio_base64;
                }
                console.error("❌ TTS failed:", data.error);
                return null;
            })
            .catch((error) => {
                console.error("❌ TTS request failed:", error);
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
            console.warn("⚠️ playAudio called with no audio data");
            return;
        }

        this.stopCurrentAudio();

        if (!this.audioUnlocked) {
            console.warn("⚠️ Audio not unlocked - playback may fail on mobile browsers");
            console.warn("💡 Unlock audio during a user interaction (click/touch) before calling playAudio()");
        }

        const base64Preview = audioBase64.substring(0, 10);
        console.log(`🔊 Starting audio playback... [${base64Preview}...]`);

        let audio;
        if (this.primedAudioForChromeIOS) {
            console.log("📱 Using gesture-primed audio element (reuse src)");
            audio = this.primedAudioForChromeIOS;

            if (!audio.paused) {
                audio.pause();
                audio.currentTime = 0;
            }

            audio.onended = null;
            audio.onerror = null;
            audio.oncanplaythrough = null;

            audio.src = `data:audio/mp3;base64,${audioBase64}`;
        } else {
            console.log("🖥️ Creating new audio element");
            audio = new Audio(`data:audio/mp3;base64,${audioBase64}`);
        }

        this.currentAudio = audio;

        return new Promise((resolve, reject) => {
            audio.onended = () => {
                console.log("✅ Audio playback ended");
                this.currentAudio = null;
                resolve();
            };
            audio.onerror = (error) => {
                console.error("❌ Audio playback error:", error);
                this.currentAudio = null;
                reject(error);
            };
            audio.play().catch(reject);
        });
    }

    restoreCache() {
        try {
            const cached = localStorage.getItem(TTS_CACHE_STORAGE_KEY);
            if (cached) {
                this.audioCache = new Map(JSON.parse(cached));
            }
        } catch (e) {
            console.warn("Failed to restore TTS cache:", e);
            this.audioCache = new Map();
        }
        try {
            localStorage.removeItem("tts_cache_v2");
        } catch {
            /* ignore */
        }
    }

    saveCache() {
        try {
            localStorage.setItem(TTS_CACHE_STORAGE_KEY, JSON.stringify([...this.audioCache]));
        } catch (e) {
            console.warn("⚠️ Failed to save TTS cache:", e);
        }
    }

    /**
     * Detect browser type for audio unlock strategy
     * @returns {string} Browser type identifier
     */
    detectBrowser() {
        const ua = navigator.userAgent;

        if (/CriOS/i.test(ua) && /iPhone|iPad|iPod/i.test(ua)) {
            return "chrome-ios";
        }

        if (/Safari/i.test(ua) && !/CriOS/i.test(ua) && /iPhone|iPad|iPod/i.test(ua)) {
            return "safari-ios";
        }

        if (/Android/i.test(ua)) {
            return /Chrome/i.test(ua) ? "android-chrome" : "android-other";
        }

        return "desktop";
    }

    isUnlocked() {
        return this.audioUnlocked;
    }

    isEnabled() {
        return this.enabled;
    }

    async unlockAudio() {
        if (this.audioUnlocked) {
            console.log("✅ Audio already unlocked");
            return true;
        }

        console.log(`🔓 Attempting to unlock audio for: ${this.browser}`);

        try {
            let success = false;

            switch (this.browser) {
                case "chrome-ios":
                    success = await this.unlockChromeIOS();
                    break;

                case "safari-ios":
                case "android-chrome":
                case "android-other":
                    success = await this.unlockMobile();
                    break;

                case "desktop":
                    success = true;
                    break;

                default:
                    success = await this.unlockMobile();
                    break;
            }

            if (success) {
                this.audioUnlocked = true;
                try {
                    sessionStorage.setItem("tts_audio_unlocked", "true");
                } catch (error) {
                    console.warn("⚠️ Could not save unlock state:", error);
                }
                console.log("✅ Audio unlocked successfully");
            }

            return success;
        } catch (error) {
            console.error("💥 Audio unlock failed:", error);
            return false;
        }
    }

    /**
     * Create and load a minimal WAV on an Audio element during a user gesture.
     * iOS Safari often allows only the first new Audio().play() after AudioContext unlock;
     * reusing one element for all TTS clips avoids NotAllowedError on word→example chains.
     */
    _primeHtmlAudioDuringGesture() {
        if (this.primedAudioForChromeIOS) {
            return;
        }
        const touchedAudio = new Audio();
        touchedAudio.volume = 1.0;
        touchedAudio.preload = "auto";
        touchedAudio.src =
            "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";
        touchedAudio.load();
        this.primedAudioForChromeIOS = touchedAudio;
    }

    async unlockChromeIOS() {
        console.log("📱 Using Chrome iOS Touch Strategy");

        try {
            this._primeHtmlAudioDuringGesture();
            console.log("✅ Chrome iOS audio element primed and ready");
            return true;
        } catch (error) {
            console.error("💥 Chrome iOS unlock failed:", error);
            return true;
        }
    }

    async unlockMobile() {
        console.log("📱 Using standard mobile AudioContext unlock + HTMLAudio priming");

        try {
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            if (!AudioContextClass) {
                console.warn("⚠️ AudioContext not supported");
                this._primeHtmlAudioDuringGesture();
                return true;
            }

            const audioContext = new AudioContextClass();

            if (audioContext.state === "suspended") {
                await audioContext.resume();
                console.log("🔊 AudioContext resumed");
            }

            const silentBuffer = audioContext.createBuffer(1, 1, 22050);
            const source = audioContext.createBufferSource();
            source.buffer = silentBuffer;
            source.connect(audioContext.destination);
            source.start();

            console.log("✅ Mobile audio unlocked via AudioContext");

            // Safari iOS (and similar): chain multiple play() only reliably on one primed element.
            this._primeHtmlAudioDuringGesture();
            console.log("✅ Gesture-primed HTMLAudio element ready for sequential playback");

            return true;
        } catch (error) {
            console.error("💥 Mobile unlock failed:", error);
            try {
                this._primeHtmlAudioDuringGesture();
            } catch {
                /* ignore */
            }
            return true;
        }
    }

    async waitForService(maxWait = 5000) {
        const deadline = Date.now() + maxWait;
        try {
            await Promise.race([
                this.initPromise,
                new Promise((resolve) => setTimeout(resolve, maxWait)),
            ]);
        } catch {
            /* ignore */
        }
        while (!this.enabled && Date.now() < deadline) {
            await new Promise((resolve) => setTimeout(resolve, 100));
        }
        return this.enabled;
    }

    stopCurrentAudio() {
        if (this.currentAudio) {
            console.log("⏹️ Stopping current audio");
            try {
                this.currentAudio.pause();
                this.currentAudio.currentTime = 0;
                this.currentAudio.onended = null;
                this.currentAudio.onerror = null;
                this.currentAudio = null;
            } catch (error) {
                console.warn("⚠️ Error stopping current audio:", error);
            }
        }
    }

    stopAllAudio() {
        console.log("🔇 Stopping ALL audio sources (comprehensive cleanup)...");

        this.stopCurrentAudio();

        if (this.primedAudioForChromeIOS) {
            try {
                console.log("🔇 Stopping primed Chrome iOS audio");
                this.primedAudioForChromeIOS.pause();
                this.primedAudioForChromeIOS.currentTime = 0;
                this.primedAudioForChromeIOS.onended = null;
                this.primedAudioForChromeIOS.onerror = null;
                this.primedAudioForChromeIOS.oncanplaythrough = null;
            } catch (error) {
                console.warn("⚠️ Error stopping primed audio:", error);
            }
        }

        try {
            const allAudioElements = document.querySelectorAll("audio");
            allAudioElements.forEach((audio) => {
                if (!audio.paused) {
                    console.log("🔇 Stopping orphaned audio element");
                    audio.pause();
                    audio.currentTime = 0;
                }
            });
        } catch (error) {
            console.warn("⚠️ Error stopping orphaned audio elements:", error);
        }
    }

    resetAudioSystem() {
        console.log("🔄 Resetting audio system for session switch...");

        this.stopAllAudio();

        console.log("🧹 Clearing pending requests");
        this.pendingRequests.clear();
    }

    clearCache() {
        this.audioCache.clear();
        this.pendingRequests.clear();
        try {
            localStorage.removeItem(TTS_CACHE_STORAGE_KEY);
            localStorage.removeItem("tts_cache_v2");
        } catch {
            /* ignore */
        }
        console.log("🗑️ Cache cleared");
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
            pending: this.pendingRequests.size,
        };

        console.log(`📊 Cache: ${stats.size} items (${stats.memoryKB}KB), ${stats.pending} pending`);
        return stats;
    }
}

window.ttsManager = TTSManager.getInstance();

window.addEventListener("beforeunload", () => {
    if (window.ttsManager) {
        window.ttsManager.cleanupForPageUnload();
    }
});
