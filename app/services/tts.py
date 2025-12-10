"""
Google Cloud Text-to-Speech service for European Portuguese.

This module provides text-to-speech functionality using Google Cloud TTS API
specifically configured for European Portuguese language learning.
"""

import base64
import hashlib
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import ClassVar

import yaml
from google.cloud import storage, texttospeech

from app.config import config
from app.session_manager import SessionKeys, SessionManager

logger = logging.getLogger(__name__)


class SupportedLanguage(Enum):
    """Supported TTS languages."""

    PT = "pt"
    EN = "en"


@dataclass
class LanguageVoiceConfig:
    """Voice configuration for a language."""

    code: str  # e.g., "pt-PT"
    voice: str  # e.g., "pt-PT-Standard-A"


class TTSService:
    """Text-to-speech service using Google Cloud TTS API."""

    # Class-level language configurations (loaded once)
    _languages: ClassVar[dict[str, LanguageVoiceConfig]] = {}

    def __init__(self):
        """Initialize TTS service and load language configurations."""
        self.tts_client = None
        self.storage_client = None
        self.bucket = None
        self.enabled = config.tts_enabled

        if self.enabled:
            self._initialize_clients()
            self._load_languages()

    def _load_languages(self) -> None:
        """Load languages.yaml into class-level dict (once)."""
        if TTSService._languages:
            return  # Already loaded

        config_path = Path(__file__).parent.parent.parent / "config" / "languages.yaml"

        if not config_path.exists():
            logger.warning(f"languages.yaml not found at {config_path}")
            return

        try:
            with open(config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            for lang_key, lang_data in data.get("languages", {}).items():
                TTSService._languages[lang_key] = LanguageVoiceConfig(
                    code=lang_data["code"], voice=lang_data["voice"]
                )

            logger.info(f"Loaded {len(TTSService._languages)} TTS languages")

        except Exception as e:
            logger.error(f"Failed to load languages.yaml: {e}")

    @property
    def voice_name(self) -> str:
        """
        Get voice name from session target language.

        Returns:
            Voice name (e.g., "pt-PT-Standard-A")

        Raises:
            ValueError: If no target language in session or language not supported
        """
        sm = SessionManager()
        target_lang = sm.get(SessionKeys.TARGET_LANGUAGE)

        if not target_lang:
            raise ValueError("No target language in session")

        lang_config = TTSService._languages.get(target_lang)

        if not lang_config:
            raise ValueError(f"Language '{target_lang}' not supported")

        return lang_config.voice

    @property
    def language_code(self) -> str:
        """
        Get language code from session target language.

        Returns:
            Language code (e.g., "pt-PT")

        Raises:
            ValueError: If no target language in session or language not supported
        """
        sm = SessionManager()
        target_lang = sm.get(SessionKeys.TARGET_LANGUAGE)

        if not target_lang:
            raise ValueError("No target language in session")

        lang_config = TTSService._languages.get(target_lang)

        if not lang_config:
            raise ValueError(f"Language '{target_lang}' not supported")

        return lang_config.code

    def _initialize_clients(self) -> None:
        """Initialize Google Cloud TTS and Storage clients."""
        try:
            # TTS client
            if config.google_cloud_service_account_file_path:
                self.tts_client = texttospeech.TextToSpeechClient.from_service_account_json(
                    config.google_cloud_service_account_file_path
                )
            else:
                self.tts_client = texttospeech.TextToSpeechClient()

            # Storage client for caching
            if config.gcs_audio_bucket:
                if config.google_cloud_service_account_file_path:
                    self.storage_client = storage.Client.from_service_account_json(
                        config.google_cloud_service_account_file_path
                    )
                else:
                    self.storage_client = storage.Client()

                self.bucket = self.storage_client.bucket(config.gcs_audio_bucket)

            logger.info("TTS service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize TTS clients: {e}")
            self.enabled = False

    def generate_speech(self, text: str) -> bytes | None:
        """
        Generate speech audio from text.

        Voice is automatically resolved from session target language.

        Args:
            text: Text to convert to speech

        Returns:
            MP3 audio bytes or None if failed
        """
        if not self.enabled or not text:
            return None

        try:
            # Configure synthesis
            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice_params = texttospeech.VoiceSelectionParams(
                language_code=self.language_code,  # From session
                name=self.voice_name,  # From session
            )
            audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)

            # Generate
            response = self.tts_client.synthesize_speech(
                input=synthesis_input, voice=voice_params, audio_config=audio_config
            )

            return response.audio_content

        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            return None

    def generate_speech_base64(self, text: str) -> str | None:
        """
        Generate speech and encode as base64.

        Args:
            text: Text to convert to speech

        Returns:
            Base64-encoded audio string or None
        """
        audio_bytes = self.generate_speech(text)
        if audio_bytes:
            return base64.b64encode(audio_bytes).decode("utf-8")
        return None

    def text_to_speech(
        self, text: str, spreadsheet_id: str = None, sheet_gid: str = None
    ) -> str | None:
        """
        Generate speech with GCS caching.

        Args:
            text: Text to convert to speech
            spreadsheet_id: For GCS cache path (optional)
            sheet_gid: For GCS cache path (optional)

        Returns:
            Base64-encoded audio string or None
        """
        if not self.enabled or not text:
            return None

        try:
            # Check GCS cache if configured
            if self.bucket and spreadsheet_id and sheet_gid:
                cache_key = self._get_cache_key(text, self.voice_name, self.language_code)
                blob_name = f"{spreadsheet_id}/{sheet_gid}/{cache_key}.mp3"
                blob = self.bucket.blob(blob_name)

                if blob.exists():
                    logger.info(f"TTS cache hit: {blob_name}")
                    audio_bytes = blob.download_as_bytes()
                    return base64.b64encode(audio_bytes).decode("utf-8")

            # Generate new audio
            audio_bytes = self.generate_speech(text)

            if not audio_bytes:
                return None

            # Cache to GCS if configured
            if self.bucket and spreadsheet_id and sheet_gid:
                try:
                    blob.upload_from_string(audio_bytes, content_type="audio/mpeg")
                    logger.info(f"TTS cached: {blob_name}")
                except Exception as e:
                    logger.warning(f"Failed to cache TTS to GCS: {e}")

            return base64.b64encode(audio_bytes).decode("utf-8")

        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            return None

    def _get_cache_key(self, text: str, voice_name: str, language_code: str) -> str:
        """Generate cache key hash."""
        cache_string = f"{text.strip()}_{voice_name}_{language_code}"
        return hashlib.sha256(cache_string.encode("utf-8")).hexdigest()

    def get_available_voices(self) -> list:
        """Get available voices for current target language."""
        if not self.enabled:
            return []

        try:
            response = self.tts_client.list_voices(language_code=self.language_code)
            return [
                {
                    "name": voice.name,
                    "language_codes": voice.language_codes,
                    "ssml_gender": texttospeech.SsmlVoiceGender(voice.ssml_gender).name,
                }
                for voice in response.voices
            ]
        except Exception as e:
            logger.error(f"Failed to fetch voices: {e}")
            return []
