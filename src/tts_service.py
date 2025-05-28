"""
Google Cloud Text-to-Speech service for European Portuguese.

This module provides text-to-speech functionality using Google Cloud TTS API
specifically configured for European Portuguese language learning.
"""

import os
import base64
import hashlib
from typing import Optional, Tuple
from google.cloud import texttospeech
from google.oauth2 import service_account
from src.config import (
    GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE, TTS_ENABLED, TTS_LANGUAGE_CODE,
    TTS_VOICE_NAME, TTS_AUDIO_ENCODING
)


class TTSService:
    """Google Cloud Text-to-Speech service wrapper"""
    
    def __init__(self):
        self.client = None
        self.enabled = TTS_ENABLED
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the Google Cloud TTS client"""
        if not self.enabled:
            print("TTS is disabled in configuration")
            return
            
        print(f"Checking for service account file: {GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE}")
        print(f"File exists: {GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE and os.path.exists(GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE) if GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE else False}")
            
        try:
            if GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE and os.path.exists(GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE):
                # Use service account file
                print(f"Loading service account from file: {GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE}")
                credentials = service_account.Credentials.from_service_account_file(
                    GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE
                )
                self.client = texttospeech.TextToSpeechClient(credentials=credentials)
                self.credential_source = "service_account_file"
                print(f"✅ TTS client initialized with service account file")
                print(f"   Service account email: {credentials.service_account_email}")
                print(f"   Project ID: {credentials.project_id}")
            else:
                # Try to use default credentials (for production with environment variables)
                print("Service account file not found, trying default credentials...")
                try:
                    self.client = texttospeech.TextToSpeechClient()
                    self.credential_source = "default_credentials"
                    print("✅ TTS client initialized with default credentials")
                    
                    # Try to get more info about default credentials
                    try:
                        import google.auth
                        default_creds, project = google.auth.default()
                        print(f"   Default credentials type: {type(default_creds).__name__}")
                        if hasattr(default_creds, 'service_account_email'):
                            print(f"   Service account email: {default_creds.service_account_email}")
                        if project:
                            print(f"   Project ID: {project}")
                    except Exception as e:
                        print(f"   Could not get default credential details: {e}")
                        
                except Exception as e:
                    print(f"❌ Failed to initialize TTS client with default credentials: {e}")
                    self.enabled = False
                    self.credential_source = "none"
                    return
                    
        except Exception as e:
            print(f"❌ Failed to initialize TTS client: {e}")
            self.enabled = False
            self.credential_source = "none"
    
    def is_available(self) -> bool:
        """Check if TTS service is available"""
        return self.enabled and self.client is not None
    
    def generate_speech(self, text: str, voice_name: Optional[str] = None) -> Optional[bytes]:
        """
        Generate speech audio from text using Google Cloud TTS
        
        Args:
            text: Text to convert to speech
            voice_name: Optional voice name override
            
        Returns:
            Audio content as bytes, or None if generation fails
        """
        if not self.is_available():
            print("TTS service is not available")
            return None
            
        if not text or not text.strip():
            print("Empty text provided for TTS")
            return None
            
        try:
            # Set the text input to be synthesized
            synthesis_input = texttospeech.SynthesisInput(text=text.strip())
            
            # Build the voice request
            voice = texttospeech.VoiceSelectionParams(
                language_code=TTS_LANGUAGE_CODE,
                name=voice_name or TTS_VOICE_NAME
            )
            
            # Select the type of audio file you want returned
            audio_config = texttospeech.AudioConfig(
                audio_encoding=getattr(texttospeech.AudioEncoding, TTS_AUDIO_ENCODING)
            )
            
            # Perform the text-to-speech request
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            
            return response.audio_content
            
        except Exception as e:
            print(f"Error generating speech: {e}")
            return None
    
    def generate_speech_base64(self, text: str, voice_name: Optional[str] = None) -> Optional[str]:
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
    
    def get_cache_key(self, text: str, voice_name: Optional[str] = None) -> str:
        """
        Generate a cache key for the given text and voice
        
        Args:
            text: Text to convert to speech
            voice_name: Optional voice name override
            
        Returns:
            Cache key string
        """
        voice = voice_name or TTS_VOICE_NAME
        cache_string = f"{text.strip()}_{voice}_{TTS_LANGUAGE_CODE}"
        return hashlib.md5(cache_string.encode('utf-8')).hexdigest()
    
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
            voices = self.client.list_voices()
            
            # Filter for Portuguese voices
            portuguese_voices = []
            for voice in voices.voices:
                for language_code in voice.language_codes:
                    if language_code.startswith('pt-PT'):
                        portuguese_voices.append({
                            'name': voice.name,
                            'language_code': language_code,
                            'gender': voice.ssml_gender.name
                        })
            
            return portuguese_voices
            
        except Exception as e:
            print(f"Error listing voices: {e}")
            return []
    
    def get_credential_info(self) -> dict:
        """Get information about which credentials are being used"""
        return {
            'source': getattr(self, 'credential_source', 'unknown'),
            'available': self.is_available(),
            'service_account_file_path': GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE,
            'service_account_file_exists': GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE and os.path.exists(GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE) if GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE else False
        }


# Global TTS service instance
tts_service = TTSService()


def generate_portuguese_speech(text: str, voice_name: Optional[str] = None) -> Optional[str]:
    """
    Convenience function to generate Portuguese speech as base64
    
    Args:
        text: Text to convert to speech
        voice_name: Optional voice name override
        
    Returns:
        Base64 encoded audio content, or None if generation fails
    """
    return tts_service.generate_speech_base64(text, voice_name)


def is_tts_available() -> bool:
    """Check if TTS service is available"""
    return tts_service.is_available()


def get_portuguese_voices() -> list:
    """Get available Portuguese voices"""
    return tts_service.get_available_voices() 