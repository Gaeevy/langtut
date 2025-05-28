/**
 * Text-to-Speech functionality for European Portuguese
 * Handles audio generation and playback using Google Cloud TTS
 */

class TTSManager {
    constructor() {
        this.isAvailable = false;
        this.voices = [];
        this.audioCache = new Map();
        this.currentAudio = null;
        this.isLoading = false;
        this.audioContext = null;
        this.userInteracted = false;
        
        // Initialize mobile audio handling
        this.initializeMobileAudio();
        
        // Initialize TTS status
        this.checkTTSStatus();
    }
    
    /**
     * Initialize mobile audio handling
     */
    initializeMobileAudio() {
        // Detect mobile
        const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
        
        if (isMobile) {
            console.log('🔊 Mobile device detected, setting up audio context');
            
            // Set up user interaction detection
            const enableAudio = () => {
                if (!this.userInteracted) {
                    console.log('🔊 User interaction detected, enabling audio');
                    this.userInteracted = true;
                    
                    // Create and play a silent audio to unlock audio context
                    const silentAudio = new Audio('data:audio/mp3;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4LjQ1LjEwMAAAAAAAAAAAAAAA//OEAAAAAAAAAAAAAAAAAAAAAAAASW5mbwAAAA8AAAAEAAABIADAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV6urq6urq6urq6urq6urq6urq6urq6urq6v////////////////////////////////8AAAAATGF2YzU4Ljk1AAAAAAAAAAAAAAAAJAAAAAAAAAAAASDs90hvAAAAAAAAAAAAAAAAAAAA//OEZAAADwAABHiAAARYiABHiAABmwQ+XAAAGmAAAAIAAANON4AABLTEFNRTMuMTAwA6q5tamtmS0odHRwOi8vd3d3LmNkZXgub3JnL3N0YXRpYy9sYW1lL2xhbWUuaHRtbAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA//OEZAAADwAABHiAAARYiABHiAABrTjOWAAAGmAAAAIAAANON4AABLTEFNRTMuMTAwA6q5tamtmS0odHRwOi8vd3d3LmNkZXgub3JnL3N0YXRpYy9sYW1lL2xhbWUuaHRtbAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA');
                    silentAudio.play().catch(() => {
                        console.log('🔊 Silent audio play failed, but user interaction registered');
                    });
                }
            };
            
            // Listen for user interactions
            ['touchstart', 'touchend', 'mousedown', 'keydown'].forEach(event => {
                document.addEventListener(event, enableAudio, { once: true, passive: true });
            });
        }
    }
    
    /**
     * Check if TTS service is available
     */
    async checkTTSStatus() {
        try {
            const response = await fetch('/api/tts/status');
            const data = await response.json();
            
            this.isAvailable = data.available;
            this.voices = data.voices || [];
            
            console.log('TTS Status:', {
                available: this.isAvailable,
                voices: this.voices.length
            });
            
            return this.isAvailable;
        } catch (error) {
            console.error('Error checking TTS status:', error);
            this.isAvailable = false;
            return false;
        }
    }
    
    /**
     * Generate and play speech for given text
     */
    async speak(text, voiceName = null) {
        if (!this.isAvailable) {
            console.warn('TTS service is not available');
            return false;
        }
        
        if (!text || !text.trim()) {
            console.warn('No text provided for TTS');
            return false;
        }
        
        // Check cache first
        const cacheKey = `${text.trim()}_${voiceName || 'default'}`;
        if (this.audioCache.has(cacheKey)) {
            return this.playAudio(this.audioCache.get(cacheKey));
        }
        
        // Show loading state
        this.setLoadingState(true);
        
        try {
            const response = await fetch('/api/tts/speak', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text: text.trim(),
                    voice_name: voiceName
                })
            });
            
            const data = await response.json();
            
            if (data.success && data.audio_base64) {
                // Cache the audio
                this.audioCache.set(cacheKey, data.audio_base64);
                
                // Play the audio
                return this.playAudio(data.audio_base64);
            } else {
                console.error('TTS generation failed:', data.error);
                return false;
            }
        } catch (error) {
            console.error('Error generating speech:', error);
            return false;
        } finally {
            this.setLoadingState(false);
        }
    }
    
    /**
     * Generate and play speech for card content (word and example)
     */
    async speakCard(word, example, voiceName = null, autoplay = false) {
        if (!this.isAvailable) {
            console.warn('TTS service is not available');
            return false;
        }
        
        this.setLoadingState(true);
        
        try {
            const response = await fetch('/api/tts/speak-card', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    word: word,
                    example: example,
                    voice_name: voiceName
                })
            });
            
            const data = await response.json();
            
            if (data.success && data.audio) {
                // Cache the audio
                if (data.audio.word) {
                    const wordCacheKey = `${word}_${voiceName || 'default'}`;
                    this.audioCache.set(wordCacheKey, data.audio.word.audio_base64);
                }
                
                if (data.audio.example) {
                    const exampleCacheKey = `${example}_${voiceName || 'default'}`;
                    this.audioCache.set(exampleCacheKey, data.audio.example.audio_base64);
                }
                
                // Play audio if autoplay is enabled
                if (autoplay) {
                    await this.playCardAudio(data.audio);
                }
                
                return data.audio;
            } else {
                console.error('TTS card generation failed:', data.error);
                return false;
            }
        } catch (error) {
            console.error('Error generating card speech:', error);
            return false;
        } finally {
            this.setLoadingState(false);
        }
    }
    
    /**
     * Play audio from base64 data
     */
    async playAudio(audioBase64) {
        try {
            // Stop current audio if playing
            this.stopCurrentAudio();
            
            // Mobile debugging
            console.log('🔊 Attempting to play audio on:', {
                userAgent: navigator.userAgent,
                isMobile: /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent),
                audioContext: typeof AudioContext !== 'undefined' || typeof webkitAudioContext !== 'undefined'
            });
            
            // Create audio element
            const audio = new Audio(`data:audio/mp3;base64,${audioBase64}`);
            this.currentAudio = audio;
            
            // Add mobile-specific audio settings
            audio.preload = 'auto';
            audio.volume = 1.0;
            
            // Mobile debugging events
            audio.addEventListener('loadstart', () => console.log('🔊 Audio loadstart'));
            audio.addEventListener('loadeddata', () => console.log('🔊 Audio loadeddata'));
            audio.addEventListener('canplay', () => console.log('🔊 Audio canplay'));
            audio.addEventListener('canplaythrough', () => console.log('🔊 Audio canplaythrough'));
            audio.addEventListener('play', () => console.log('🔊 Audio play event'));
            audio.addEventListener('playing', () => console.log('🔊 Audio playing'));
            audio.addEventListener('pause', () => console.log('🔊 Audio paused'));
            audio.addEventListener('ended', () => {
                console.log('🔊 Audio ended');
                this.currentAudio = null;
            });
            audio.addEventListener('error', (e) => {
                console.error('🔊 Audio error:', e);
                console.error('🔊 Audio error details:', {
                    error: audio.error,
                    networkState: audio.networkState,
                    readyState: audio.readyState
                });
            });
            
            // Wait for audio to be ready
            await new Promise((resolve, reject) => {
                const timeout = setTimeout(() => {
                    reject(new Error('Audio loading timeout'));
                }, 10000); // 10 second timeout
                
                audio.addEventListener('canplaythrough', () => {
                    clearTimeout(timeout);
                    resolve();
                }, { once: true });
                
                audio.addEventListener('error', () => {
                    clearTimeout(timeout);
                    reject(new Error('Audio loading failed'));
                });
                
                // Start loading
                audio.load();
            });
            
            console.log('🔊 Audio ready, attempting to play...');
            
            // Try to play the audio
            const playPromise = audio.play();
            
            if (playPromise !== undefined) {
                await playPromise;
                console.log('🔊 Audio play promise resolved successfully');
            }
            
            return true;
        } catch (error) {
            console.error('🔊 Error playing audio:', error);
            
            // Mobile-specific error handling
            if (error.name === 'NotAllowedError') {
                console.error('🔊 Audio blocked by browser autoplay policy');
                alert('Audio is blocked by your browser. Please tap the audio button manually to enable sound.');
            } else if (error.name === 'NotSupportedError') {
                console.error('🔊 Audio format not supported');
                alert('Audio format not supported on this device.');
            } else {
                console.error('🔊 Unknown audio error:', error.message);
            }
            
            return false;
        }
    }
    
    /**
     * Play card audio with delay between word and example
     */
    async playCardAudio(audioData, delay = 1000) {
        try {
            // Play word first
            if (audioData.word) {
                await this.playAudio(audioData.word.audio_base64);
                
                // Wait for word to finish + delay
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
            console.error('Error playing card audio:', error);
            return false;
        }
    }
    
    /**
     * Stop currently playing audio
     */
    stopCurrentAudio() {
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio.currentTime = 0;
            this.currentAudio = null;
        }
    }
    
    /**
     * Set loading state for UI feedback
     */
    setLoadingState(loading) {
        this.isLoading = loading;
        
        // Update minimal audio buttons
        const minimalButtons = document.querySelectorAll('.btn-audio-minimal');
        minimalButtons.forEach(btn => {
            if (loading) {
                btn.disabled = true;
                btn.innerHTML = '<i class="bi bi-hourglass-split"></i>';
            } else {
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-volume-up"></i>';
            }
        });
        
        // Update legacy TTS buttons (for other pages)
        const speakButtons = document.querySelectorAll('.tts-speak-btn:not(.btn-audio-minimal)');
        speakButtons.forEach(btn => {
            if (loading) {
                btn.disabled = true;
                btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Loading...';
            } else {
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-volume-up"></i> Listen';
            }
        });
    }
    
    /**
     * Create a speak button for text
     */
    createSpeakButton(text, className = 'btn btn-outline-primary btn-sm tts-speak-btn') {
        const button = document.createElement('button');
        button.className = className;
        button.innerHTML = '<i class="bi bi-volume-up"></i> Listen';
        button.title = 'Listen to pronunciation';
        
        button.addEventListener('click', async (e) => {
            e.preventDefault();
            await this.speak(text);
        });
        
        return button;
    }
    
    /**
     * Add speak buttons to elements with data-tts attribute
     */
    initializeSpeakButtons() {
        const elements = document.querySelectorAll('[data-tts]');
        elements.forEach(element => {
            const text = element.getAttribute('data-tts') || element.textContent;
            if (text && text.trim()) {
                const button = this.createSpeakButton(text.trim());
                
                // Add button after the element
                element.parentNode.insertBefore(button, element.nextSibling);
            }
        });
    }
    
    /**
     * Clear audio cache
     */
    clearCache() {
        this.audioCache.clear();
        console.log('TTS audio cache cleared');
    }
    
    /**
     * Get cache statistics
     */
    getCacheStats() {
        return {
            size: this.audioCache.size,
            keys: Array.from(this.audioCache.keys())
        };
    }
}

// Global TTS manager instance
window.ttsManager = new TTSManager();

// Auto-initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    if (window.ttsManager.isAvailable) {
        window.ttsManager.initializeSpeakButtons();
    }
});

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TTSManager;
} 