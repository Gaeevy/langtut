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
        
        // Initialize TTS status
        this.checkTTSStatus();
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
            
            // Create audio element
            const audio = new Audio(`data:audio/mp3;base64,${audioBase64}`);
            this.currentAudio = audio;
            
            // Play the audio
            await audio.play();
            
            // Clean up when finished
            audio.addEventListener('ended', () => {
                this.currentAudio = null;
            });
            
            return true;
        } catch (error) {
            console.error('Error playing audio:', error);
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