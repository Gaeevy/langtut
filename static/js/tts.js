/**
 * Minimalistic TTS Manager with persistent caching
 */
class TTSManager {
    constructor() {
        this.isAvailable = false;
        this.audioCache = new Map();
        this.currentAudio = null;
        this.pendingRequests = new Map();

        // Restore cache from sessionStorage
        this.restoreCache();

        // Check TTS availability and setup mobile audio
        this.init();
    }

    async init() {
        // Check TTS service
        try {
            const response = await fetch('/api/tts/status');
            const data = await response.json();
            this.isAvailable = data.available;
        } catch (error) {
            console.error('❌ TTS init failed:', error);
        }

        // Setup mobile audio unlock
        if (/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)) {
            const unlock = () => {
                const audio = new Audio('data:audio/mp3;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4LjQ1LjEwMAAAAAAAAAAAAAAA//OEAAAAAAAAAAAAAAAAAAAAAAAASW5mbwAAAA8AAAAEAAABIADAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV6urq6urq6urq6urq6urq6urq6urq6v////////////////////////////////8AAAAATGF2YzU4Ljk1AAAAAAAAAAAAAAAAJAAAAAAAAAAAASDs90hvAAAAAAAAAAAAAAAAAAAA//OEZAAADwAABHiAAARYiABHiAABmwQ+XAAAGmAAAAIAAANON4AABLTEFNRTMuMTAwA6q5tamtmS0odHRwOi8vd3d3LmNkZXgub3JnL3N0YXRpYy9sYW1lL2xhbWUuaHRtbAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA//OEZAAADwAABHiAAARYiABHiAABrTjOWAAAGmAAAAIAAANON4AABLTEFNRTMuMTAwA6q5tamtmS0odHRwOi8vd3d3LmNkZXgub3JnL3N0YXRpYy9sYW1lL2xhbWUuaHRtbAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA');
                audio.play().catch(() => {});
            };
            ['touchstart', 'mousedown', 'keydown'].forEach(event =>
                document.addEventListener(event, unlock, { once: true, passive: true })
            );
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

            if (autoplay) {
                const audioData = {};
                if (word) audioData.word = { audio_base64: this.audioCache.get(wordKey) };
                if (example) audioData.example = { audio_base64: this.audioCache.get(exampleKey) };
                await this.playCardAudio(audioData);
            }
            return true;
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
            this.stopCurrentAudio();

            const audio = new Audio(`data:audio/mp3;base64,${audioBase64}`);
            this.currentAudio = audio;

            audio.addEventListener('ended', () => this.currentAudio = null);
            audio.addEventListener('error', (e) => console.error('💥 Audio error:', e));

            // Wait for ready and play
            await new Promise((resolve, reject) => {
                const timeout = setTimeout(() => reject(new Error('Timeout')), 10000);

                audio.addEventListener('canplaythrough', () => {
                    clearTimeout(timeout);
                    resolve();
                }, { once: true });

                audio.addEventListener('error', () => {
                    clearTimeout(timeout);
                    reject(new Error('Load failed'));
                });

                audio.load();
            });

            await audio.play();
            return true;
        } catch (error) {
            console.error('💥 Playback error:', error);

            if (error.name === 'NotAllowedError') {
                alert('Audio blocked. Please tap the audio button manually.');
            }
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
            this.currentAudio.pause();
            this.currentAudio.currentTime = 0;
            this.currentAudio = null;
        }
    }

    // Legacy speak method for compatibility
    async speak(text, voice = null) {
        return this.speakCard(text, null, voice, true);
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
