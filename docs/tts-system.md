# Text-to-Speech System

## Overview
The TTS system provides European Portuguese audio generation for language learning flashcards. It integrates Google Cloud Text-to-Speech API with comprehensive caching, mobile optimization, and robust error handling.

**Current Status:** ✅ Production Ready - Full implementation with Google Cloud TTS, GCS caching, and mobile support

## Core Features

### Google Cloud TTS Integration
- **European Portuguese Voice:** Optimized for `pt-PT-Standard-A` voice
- **High-Quality Audio:** MP3 encoding for optimal quality and size
- **Service Account Authentication:** Secure credential management
- **Rate Limiting Handling:** Automatic retry and backoff strategies

### Audio Caching System
- **Google Cloud Storage:** Persistent audio caching in GCS bucket
- **Memory Caching:** Client-side Map-based cache for instant playback
- **Cache Key Generation:** Deterministic keys for efficient lookups
- **Cache Invalidation:** Automatic cleanup and refresh mechanisms

### Mobile Optimization
- **Autoplay Solutions:** Browser-specific audio unlock strategies
- **Chrome iOS Support:** Specialized "Touch Strategy" for strict autoplay policies
- **Audio Element Management:** Proper cleanup and resource management
- **Background Audio:** Seamless audio playback without interruptions

## Architecture

### Backend Components

#### TTS Service (`src/tts_service.py`)
- **Google Cloud TTS Client:** Authenticated API client
- **Audio Generation:** Text-to-speech synthesis
- **GCS Integration:** Audio file storage and retrieval
- **Error Handling:** Comprehensive exception handling and logging

#### API Endpoints (`src/routes/api.py`)
- **`/api/tts`:** Main TTS endpoint for audio generation
- **Request Processing:** Input validation and sanitization
- **Response Formatting:** JSON responses with base64 audio
- **Authentication:** User authentication and authorization

### Frontend Components

#### TTSManager (`static/js/tts.js`)
- **Audio Playback:** HTML5 Audio element management
- **Cache Management:** Client-side audio caching
- **Mobile Unlock:** Device-specific audio unlock strategies
- **Error Recovery:** Fallback mechanisms and retry logic

#### Audio Controls
- **Play Buttons:** Individual word and example audio controls
- **Automatic Playback:** Feedback page auto-play functionality
- **Volume Control:** User-adjustable audio volume
- **Speed Control:** Playback speed adjustment (future feature)

## TTS Service Implementation

### Google Cloud Configuration
```python
class TTSService:
    def __init__(self):
        self.client = texttospeech.TextToSpeechClient(
            credentials=service_account_credentials
        )
        self.bucket = storage.Client(
            credentials=service_account_credentials
        ).bucket(config.GCS_AUDIO_BUCKET)

    def generate_audio(self, text: str, voice_name: str = None) -> bytes:
        """Generate audio using Google Cloud TTS."""
        synthesis_input = texttospeech.SynthesisInput(text=text)

        voice = texttospeech.VoiceSelectionParams(
            language_code=config.TTS_LANGUAGE_CODE,
            name=voice_name or config.TTS_VOICE_NAME
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        response = self.client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        return response.audio_content
```

### Caching Strategy
```python
async def get_or_generate_audio(self, text: str, voice_name: str = None) -> dict:
    """Get audio from cache or generate if not cached."""
    cache_key = self.generate_cache_key(text, voice_name)

    # Check GCS cache first
    if self.is_cached_in_gcs(cache_key):
        audio_data = self.get_from_gcs_cache(cache_key)
        return {
            'audio_base64': base64.b64encode(audio_data).decode('utf-8'),
            'cached': True,
            'cache_source': 'gcs'
        }

    # Generate new audio
    audio_data = self.generate_audio(text, voice_name)

    # Cache in GCS for persistence
    self.cache_in_gcs(cache_key, audio_data)

    return {
        'audio_base64': base64.b64encode(audio_data).decode('utf-8'),
        'cached': False,
        'cache_source': 'generated'
    }
```

## API Endpoints

### POST /api/tts
Main TTS endpoint for generating audio.

**Request:**
```json
{
    "text": "Olá mundo",
    "voice_name": "pt-PT-Standard-A",
    "spreadsheet_id": "1ABC123...",
    "sheet_gid": "123456789"
}
```

**Response:**
```json
{
    "success": true,
    "audio_base64": "SUQzAwAAAZYAAAAAAABQUklWAAAACgAAAABQZWFrAAABNQA...",
    "text": "Olá mundo",
    "language": "pt-PT",
    "voice_name": "pt-PT-Standard-A",
    "cached": true,
    "cache_source": "gcs",
    "audio_length_seconds": 2.5,
    "metadata": {
        "spreadsheet_id": "1ABC123...",
        "sheet_gid": "123456789",
        "generation_time": "2024-01-15T10:30:00Z"
    }
}
```

### Specialized Endpoints

#### Card Audio Generation
```python
@api_bp.route('/api/tts/card', methods=['POST'])
def generate_card_audio():
    """Generate audio for both word and example simultaneously."""
    word_audio = await tts_service.get_or_generate_audio(card.word)
    example_audio = await tts_service.get_or_generate_audio(card.example)

    return jsonify({
        'success': True,
        'word': word_audio,
        'example': example_audio,
        'card_id': card.id
    })
```

## Frontend Implementation

### TTSManager Class
```javascript
class TTSManager {
    constructor() {
        this.audioCache = new Map();
        this.currentAudio = null;
        this.userInteracted = false;
        this.primedAudioForChromeIOS = null;
    }

    async speak(text, voiceName = null) {
        // Check client-side cache first
        const cacheKey = `${text}_${voiceName || 'default'}`;

        if (this.audioCache.has(cacheKey)) {
            return this.playAudio(this.audioCache.get(cacheKey));
        }

        // Generate audio via API
        const response = await fetch('/api/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, voice_name: voiceName })
        });

        const data = await response.json();

        if (data.success) {
            // Cache for future use
            this.audioCache.set(cacheKey, data.audio_base64);
            return this.playAudio(data.audio_base64);
        }
    }

    async playAudio(audioBase64) {
        // Use primed audio element for Chrome iOS
        let audio = this.primedAudioForChromeIOS || new Audio();
        audio.src = `data:audio/mp3;base64,${audioBase64}`;

        try {
            await audio.play();
            return true;
        } catch (error) {
            console.error('Audio playback failed:', error);
            return false;
        }
    }
}
```

### Mobile Audio Unlock
```javascript
// Chrome iOS Touch Strategy
async unlockAudioForChromeIOS() {
    const touchedAudio = new Audio();
    touchedAudio.volume = 1.0;
    touchedAudio.preload = 'auto';

    // Load silent audio to "touch" the audio subsystem
    touchedAudio.src = 'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=';
    touchedAudio.load();

    // Store for reuse
    this.primedAudioForChromeIOS = touchedAudio;
    return true;
}

// Safari iOS/General Mobile Unlock
async unlockAudioContext() {
    if (!this.audioContext) {
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }

    if (this.audioContext.state === 'suspended') {
        await this.audioContext.resume();
    }

    // Play silent buffer to unlock
    const silentBuffer = this.audioContext.createBuffer(1, 1, 22050);
    const source = this.audioContext.createBufferSource();
    source.buffer = silentBuffer;
    source.connect(this.audioContext.destination);
    source.start();

    return true;
}
```

## Configuration

### Environment Variables
```toml
# settings.toml
[default]
tts_enabled = true
tts_language_code = "pt-PT"
tts_voice_name = "pt-PT-Standard-A"
tts_audio_encoding = "MP3"
gcs_audio_bucket = "langtut-tts"
google_cloud_service_account_file = "google-cloud-service-account.json"

[production]
# Production uses environment variables
# LANGTUT_GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON = "{"type":"service_account",...}"
```

### Service Account Setup
```json
{
    "type": "service_account",
    "project_id": "your-project-id",
    "private_key_id": "your-key-id",
    "private_key": "REPLACE_WITH_YOUR_ACTUAL_PRIVATE_KEY_FROM_GOOGLE_CLOUD",
    "client_email": "tts-service@your-project.iam.gserviceaccount.com",
    "client_id": "123456789",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token"
}
```

## Caching System

### GCS Bucket Configuration
- **Bucket Name:** `langtut-tts`
- **Location:** Regional (optimized for application location)
- **Storage Class:** Standard (for frequent access)
- **Lifecycle Policy:** Automatic cleanup of old cache entries

### Cache Key Generation
```python
def generate_cache_key(self, text: str, voice_name: str = None) -> str:
    """Generate deterministic cache key for audio content."""
    voice = voice_name or self.config.TTS_VOICE_NAME
    content = f"{text}_{voice}_{self.config.TTS_LANGUAGE_CODE}"
    return hashlib.md5(content.encode('utf-8')).hexdigest()
```

### Cache Invalidation
```python
def invalidate_cache(self, text: str, voice_name: str = None):
    """Invalidate cache entry for specific text."""
    cache_key = self.generate_cache_key(text, voice_name)

    # Remove from GCS
    try:
        blob = self.bucket.blob(cache_key)
        blob.delete()
    except Exception as e:
        logger.warning(f"Failed to delete cache entry: {e}")
```

## Error Handling

### Backend Error Handling
```python
@api_bp.route('/api/tts', methods=['POST'])
def text_to_speech():
    try:
        # Input validation
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'success': False, 'error': 'Text is required'}), 400

        # Generate audio
        result = tts_service.get_or_generate_audio(data['text'])

        return jsonify({
            'success': True,
            **result
        })

    except GoogleCloudError as e:
        logger.error(f"Google Cloud TTS error: {e}")
        return jsonify({
            'success': False,
            'error': 'TTS service temporarily unavailable'
        }), 503

    except Exception as e:
        logger.error(f"Unexpected TTS error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500
```

### Frontend Error Handling
```javascript
async speak(text, voiceName = null) {
    try {
        const response = await fetch('/api/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, voice_name: voiceName })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'TTS generation failed');
        }

        return this.playAudio(data.audio_base64);

    } catch (error) {
        console.error('TTS error:', error);
        this.showError('Audio generation failed. Please try again.');
        return false;
    }
}
```

## Performance Optimization

### Caching Strategy
- **Two-Tier Caching:** Client-side Map cache + GCS persistent cache
- **Cache-First:** Always check cache before generating new audio
- **Background Prefetching:** Preload likely audio content
- **Memory Management:** Automatic cleanup of old cache entries

### API Optimization
- **Batch Requests:** Multiple audio generation in single request
- **Connection Pooling:** Reuse HTTP connections to Google Cloud
- **Compression:** Gzip compression for API responses
- **Rate Limiting:** Prevent API quota exhaustion

### Audio Optimization
- **Optimal Encoding:** MP3 for best quality/size ratio
- **Bitrate Selection:** Balanced quality and file size
- **Streaming Support:** Progressive audio loading
- **Preloading:** Strategic audio preloading for better UX

## Security Considerations

### Authentication
- **Service Account:** Secure Google Cloud authentication
- **User Authentication:** TTS access requires user login
- **Request Validation:** All inputs validated and sanitized
- **Rate Limiting:** Prevent abuse and quota exhaustion

### Data Protection
- **No PII Storage:** Only audio content cached, no personal data
- **Secure Transmission:** HTTPS for all API communication
- **Credential Management:** Environment variables for sensitive data
- **Audit Logging:** All TTS requests logged for security monitoring

## Testing

### Unit Tests
```python
def test_tts_generation():
    """Test basic TTS audio generation."""
    result = tts_service.get_or_generate_audio("Olá mundo")

    assert result['success'] is True
    assert 'audio_base64' in result
    assert result['text'] == "Olá mundo"
    assert result['language'] == "pt-PT"
```

### Integration Tests
```python
def test_tts_api_endpoint():
    """Test TTS API endpoint."""
    response = client.post('/api/tts', json={'text': 'Teste'})

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'audio_base64' in data
```

### Frontend Tests
```javascript
test('TTSManager audio playback', async () => {
    const ttsManager = new TTSManager();
    const result = await ttsManager.speak('Olá');

    expect(result).toBe(true);
    expect(ttsManager.audioCache.has('Olá_default')).toBe(true);
});
```

## Monitoring and Analytics

### Performance Metrics
- **Cache Hit Rate:** Percentage of requests served from cache
- **Generation Time:** Average time to generate new audio
- **API Response Time:** End-to-end API response times
- **Error Rate:** Percentage of failed requests

### Usage Analytics
- **Popular Phrases:** Most frequently requested audio
- **Language Usage:** Distribution of language requests
- **User Engagement:** Audio playback patterns
- **Device Statistics:** Mobile vs desktop usage

### Alerting
- **High Error Rate:** Alert when error rate exceeds threshold
- **Quota Exhaustion:** Monitor Google Cloud API usage
- **Cache Performance:** Alert on poor cache hit rates
- **Service Availability:** Monitor TTS service uptime

## Future Enhancements

### Voice Options
- **Multiple Voices:** Support for different Portuguese voices
- **Voice Selection:** User preference for voice selection
- **Speed Control:** Adjustable playback speed
- **Pitch Control:** Voice pitch adjustment

### Advanced Features
- **SSML Support:** Speech Synthesis Markup Language
- **Audio Effects:** Reverb, echo, and other audio effects
- **Pronunciation Guides:** Phonetic transcriptions
- **Word Highlighting:** Synchronized text highlighting

### Performance Improvements
- **Streaming Audio:** Real-time audio streaming
- **Edge Caching:** CDN-based audio caching
- **Predictive Caching:** Machine learning-based cache preloading
- **Compression:** Advanced audio compression techniques
