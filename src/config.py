"""
Unified configuration management for Language Learning Flashcard App.

Single source of truth for all configuration with environment-aware settings
and simplified credential handling (env vars first, then file paths).
"""

import os
from enum import StrEnum

from dynaconf import Dynaconf
from pydantic_settings import BaseSettings

from src.logging import setup_logging
from src.utils import resolve_secrets_file_path


class Environment(StrEnum):
    PRODUCTION = "production"
    LOCAL = "local"


def resolve_environment() -> Environment:
    """Environment detection using Railway's automatic variables.

    Returns:
        str: 'production' or 'local'
    """
    # Production environment - Railway sets RAILWAY_ENVIRONMENT automatically
    if os.getenv("RAILWAY_ENVIRONMENT") == "production":
        return Environment.PRODUCTION

    # Default to local development
    return Environment.LOCAL


# Initialize logging
logger = setup_logging()

# Load configuration based on environment
_environment = resolve_environment()
logger.info(f"Detected environment: {_environment}")

# Load settings from TOML files
_settings = Dynaconf(
    envvar_prefix="LANGTUT",
    settings_files=["settings.toml", ".secrets.toml"],
    environments=True,
    env=_environment,
    load_dotenv=True,
)

_client_secrets_file_path = resolve_secrets_file_path(
    _settings.get("client_secret_json"),
    _settings.get("client_secrets_file"),
)
_google_cloud_service_account_file_path = resolve_secrets_file_path(
    _settings.get("google_cloud_service_account_json"),
    _settings.get("google_cloud_service_account_file"),
)


class Config(BaseSettings):
    """Unified configuration using Pydantic.

    Single source of truth for all application settings with environment-aware
    configuration and simplified credential handling.

    Credentials are loaded with priority:
    1. Environment variable (JSON string for Railway)
    2. File path (for local development)
    """

    # Environment
    environment: Environment = _environment
    debug: bool = _settings["debug"]

    # Core app
    secret_key: str | None = _settings.get("SECRET_KEY")
    max_cards_per_session: int = _settings["max_cards_per_session"]
    spreadsheet_id: str = _settings["spreadsheet_id"]

    # Database
    database_path: str = _settings["database_path"]

    # Flask Session
    session_type: str = _settings["session_type"]
    session_permanent: bool = _settings["session_permanent"]
    session_use_signer: bool = _settings["session_use_signer"]
    session_cookie_secure: bool = _settings["session_cookie_secure"]
    session_cookie_httponly: bool = _settings["session_cookie_httponly"]
    session_cookie_samesite: str = _settings["session_cookie_samesite"]

    # Flask JSON
    json_as_ascii: bool = _settings["json_as_ascii"]

    # Google OAuth
    scopes: list[str] = _settings["scopes"]
    api_service_name: str = _settings["api_service_name"]
    api_version: str = _settings["api_version"]

    # Google TTS
    tts_enabled: bool = _settings["tts_enabled"]
    tts_language_code: str = _settings["tts_language_code"]
    tts_voice_name: str = _settings["tts_voice_name"]
    tts_audio_encoding: str = _settings["tts_audio_encoding"]
    gcs_audio_bucket: str = _settings["gcs_audio_bucket"]

    # Credentials
    client_secrets_file_path: str = _client_secrets_file_path
    google_cloud_service_account_file_path: str = _google_cloud_service_account_file_path


# Export single config object
config = Config()
