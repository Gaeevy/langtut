"""
Google Cloud Text-to-Speech service for European Portuguese.

This module provides text-to-speech functionality using Google Cloud TTS API
specifically configured for European Portuguese language learning.
"""

import base64
import hashlib
import logging
import os

from google.cloud import storage, texttospeech
from google.oauth2 import service_account

from src.config import config, settings

# Create logger
logger = logging.getLogger(__name__)


class TTSService:
    """Google Cloud Text-to-Speech service wrapper with GCS caching"""

    def __init__(self):
        self.tts_client = None
        self.storage_client = None
        self.bucket = None
        self.enabled = config.TTS_ENABLED
        self._initialize_clients()

    def _initialize_clients(self):
        """Initialize the Google Cloud TTS and Storage clients"""
        if not self.enabled:
            logger.info('TTS is disabled in configuration')
            return

        logger.info(
            f'Checking for service account file: {config.GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE}'
        )
        logger.info(
            f'File exists: {config.GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE and os.path.exists(config.GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE) if config.GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE else False}'
        )

        try:
            if config.GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE and os.path.exists(
                config.GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE
            ):
                # Use service account file
                logger.info(
                    f'Loading service account from file: {config.GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE}'
                )
                credentials = service_account.Credentials.from_service_account_file(
                    config.GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE
                )
                self.tts_client = texttospeech.TextToSpeechClient(credentials=credentials)
                self.storage_client = storage.Client(credentials=credentials)
                self.credential_source = 'service_account_file'
                logger.info('✅ TTS client initialized with service account file')
                logger.info(f'   Service account email: {credentials.service_account_email}')
                logger.info(f'   Project ID: {credentials.project_id}')
            else:
                # Try to use default credentials (for production with environment variables)
                logger.info('Service account file not found, trying default credentials...')
                try:
                    self.tts_client = texttospeech.TextToSpeechClient()
                    self.storage_client = storage.Client()
                    self.credential_source = 'default_credentials'
                    logger.info('✅ TTS client initialized with default credentials')

                    # Try to get more info about default credentials
                    try:
                        import google.auth

                        default_creds, project = google.auth.default()
                        logger.info(f'   Default credentials type: {type(default_creds).__name__}')
                        if hasattr(default_creds, 'service_account_email'):
                            logger.info(
                                f'   Service account email: {default_creds.service_account_email}'
                            )
                        if project:
                            logger.info(f'   Project ID: {project}')
                    except Exception as e:
                        logger.info(f'   Could not get default credential details: {e}')

                except Exception as e:
                    logger.error(
                        f'❌ Failed to initialize TTS client with default credentials: {e}'
                    )
                    self.enabled = False
                    self.credential_source = 'none'
                    return

            # Initialize GCS bucket for audio caching
            try:
                bucket_name = settings.get('GCS_AUDIO_BUCKET', 'langtut-tts')
                self.bucket = self.storage_client.bucket(bucket_name)
                logger.info(f'✅ GCS bucket initialized: {bucket_name}')
            except Exception as e:
                logger.warning(f'⚠️ GCS bucket initialization failed: {e}')
                logger.warning('   Continuing without GCS caching...')
                self.bucket = None

        except Exception as e:
            logger.error(f'❌ Failed to initialize TTS client: {e}')
            self.enabled = False
            self.credential_source = 'none'

    def is_available(self) -> bool:
        """Check if TTS service is available"""
        return self.enabled and self.tts_client is not None

    def generate_speech(self, text: str, voice_name: str | None = None) -> bytes | None:
        """
        Generate speech audio from text using Google Cloud TTS

        Args:
            text: Text to convert to speech
            voice_name: Optional voice name override

        Returns:
            Audio content as bytes, or None if generation fails
        """
        if not self.is_available():
            logger.info('TTS service is not available')
            return None

        if not text or not text.strip():
            logger.info('Empty text provided for TTS')
            return None

        try:
            # Set the text input to be synthesized
            synthesis_input = texttospeech.SynthesisInput(text=text.strip())

            # Build the voice request
            voice = texttospeech.VoiceSelectionParams(
                language_code=config.TTS_LANGUAGE_CODE, name=voice_name or config.TTS_VOICE_NAME
            )

            # Select the type of audio file you want returned
            audio_config = texttospeech.AudioConfig(
                audio_encoding=getattr(texttospeech.AudioEncoding, config.TTS_AUDIO_ENCODING)
            )

            # Perform the text-to-speech request
            response = self.tts_client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )

            return response.audio_content

        except Exception as e:
            logger.error(f'Error generating speech: {e}')
            return None

    def generate_speech_base64(self, text: str, voice_name: str | None = None) -> str | None:
        """
        Generate speech and return as base64 encoded string for web use

        Args:
            text: Text to convert to speech
            voice_name: Optional voice name override

        Returns:
            Base64 encoded audio content, or None if generation fails
        """
        audio_content = self.generate_speech(text, voice_name)
        if audio_content:
            return base64.b64encode(audio_content).decode('utf-8')
        return None

    def get_cache_key(self, text: str, voice_name: str | None = None) -> str:
        """
        Generate cache key for TTS audio based on text and voice

        Args:
            text: Text to be spoken
            voice_name: Voice name for TTS

        Returns:
            Cache key string (MD5 hash)
        """
        voice = voice_name or config.TTS_VOICE_NAME
        cache_string = f'{text.strip()}_{voice}_{config.TTS_LANGUAGE_CODE}'
        return hashlib.md5(cache_string.encode('utf-8'), usedforsecurity=False).hexdigest()

    def get_gcs_path(
        self, spreadsheet_id: str, sheet_gid: int, text: str, voice_name: str | None = None
    ) -> str:
        """
        Generate GCS path for audio file using spreadsheet_id/sheet_gid/text_hash structure

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_gid: Google Sheets worksheet GID (permanent ID)
            text: Text to convert to speech
            voice_name: Optional voice name override

        Returns:
            GCS path string
        """
        text_hash = self.get_cache_key(text, voice_name)
        return f'{spreadsheet_id}/{sheet_gid}/{text_hash}.mp3'

    def get_audio_from_gcs(
        self, spreadsheet_id: str, sheet_gid: int, text: str, voice_name: str | None = None
    ) -> bytes | None:
        """
        Try to get cached audio from GCS

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_gid: Google Sheets worksheet GID
            text: Text to convert to speech
            voice_name: Optional voice name override

        Returns:
            Audio content as bytes if cached, None if not found
        """
        if not self.bucket:
            return None

        try:
            gcs_path = self.get_gcs_path(spreadsheet_id, sheet_gid, text, voice_name)
            blob = self.bucket.blob(gcs_path)

            if blob.exists():
                logger.debug(f'🎯 Cache HIT: {gcs_path}')
                return blob.download_as_bytes()
            else:
                logger.debug(f'🎯 Cache MISS: {gcs_path}')
                return None

        except Exception as e:
            logger.warning(f'⚠️ Error checking GCS cache: {e}')
            return None

    def cache_audio_to_gcs(
        self,
        spreadsheet_id: str,
        sheet_gid: int,
        text: str,
        audio_content: bytes,
        voice_name: str | None = None,
    ) -> bool:
        """
        Cache audio content to GCS

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_gid: Google Sheets worksheet GID
            text: Text to convert to speech
            audio_content: Audio content as bytes
            voice_name: Optional voice name override

        Returns:
            True if successfully cached, False otherwise
        """
        if not self.bucket or not audio_content:
            return False

        try:
            gcs_path = self.get_gcs_path(spreadsheet_id, sheet_gid, text, voice_name)
            blob = self.bucket.blob(gcs_path)

            # Upload with MP3 content type
            blob.upload_from_string(audio_content, content_type='audio/mpeg')
            logger.info(f'💾 Cached audio: {gcs_path}')
            return True

        except Exception as e:
            logger.warning(f'⚠️ Error caching audio to GCS: {e}')
            return False

    def text_to_speech(
        self,
        text: str,
        spreadsheet_id: str = None,
        sheet_gid: int = None,
        voice_name: str | None = None,
    ) -> str | None:
        """
        Generate speech with GCS caching support (returns base64)

        Args:
            text: Text to convert to speech
            spreadsheet_id: Google Sheets spreadsheet ID for caching
            sheet_gid: Google Sheets worksheet GID for caching
            voice_name: Optional voice name override

        Returns:
            Base64 encoded audio content, or None if generation fails
        """
        if not self.is_available():
            logger.warning('TTS service is not available')
            return None

        if not text or not text.strip():
            logger.info('Empty text provided for TTS')
            return None

        # Try to get from cache first (if we have caching context)
        if spreadsheet_id and sheet_gid is not None:
            cached_audio = self.get_audio_from_gcs(spreadsheet_id, sheet_gid, text, voice_name)
            if cached_audio:
                return base64.b64encode(cached_audio).decode('utf-8')

        # Generate new audio via TTS API
        audio_content = self.generate_speech(text, voice_name)
        if not audio_content:
            return None

        # Cache the audio (if we have caching context)
        if spreadsheet_id and sheet_gid is not None:
            self.cache_audio_to_gcs(spreadsheet_id, sheet_gid, text, audio_content, voice_name)

        # Return base64 encoded audio
        return base64.b64encode(audio_content).decode('utf-8')

    def get_available_voices(self) -> list:
        """
        Get list of available Portuguese voices

        Returns:
            List of available voice names for Portuguese
        """
        if not self.is_available():
            return []

        try:
            # List available voices
            voices = self.tts_client.list_voices()

            # Filter for Portuguese voices
            portuguese_voices = []
            for voice in voices.voices:
                for language_code in voice.language_codes:
                    if language_code.startswith('pt-PT'):
                        portuguese_voices.append(
                            {
                                'name': voice.name,
                                'language_code': language_code,
                                'gender': voice.ssml_gender.name,
                            }
                        )

            return portuguese_voices

        except Exception as e:
            logger.error(f'Error listing voices: {e}')
            return []

    def get_credential_info(self) -> dict:
        """Get information about which credentials are being used"""
        return {
            'source': getattr(self, 'credential_source', 'unknown'),
            'available': self.is_available(),
            'service_account_file_path': config.GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE,
            'service_account_file_exists': config.GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE
            and os.path.exists(config.GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE)
            if config.GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE
            else False,
        }


# Global TTS service instance
tts_service = TTSService()


def is_tts_available() -> bool:
    """Check if TTS service is available"""
    return tts_service.is_available()


def get_portuguese_voices() -> list:
    """Get available Portuguese voices"""
    return tts_service.get_available_voices()
