"""
Unified configuration management for Language Learning Flashcard App.

Single source of truth for all configuration with environment-aware settings
and simplified credential handling (env vars first, then file paths).
"""

import json
import logging
import os
import sys
import tempfile
from pathlib import Path

from dynaconf import Dynaconf
from pydantic import computed_field
from pydantic_settings import BaseSettings


def setup_logging() -> logging.Logger:
    """Configure logging for both local development and Railway deployment."""
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create formatter with milliseconds for performance debugging
    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler (works on both local and Railway)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Set specific logger levels
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient.discovery").setLevel(logging.WARNING)

    return logger


def get_environment() -> str:
    """
    Environment detection using Railway's automatic variables.

    Returns:
        str: 'production' or 'local'
    """
    # Production environment - Railway sets RAILWAY_ENVIRONMENT automatically
    if os.getenv("RAILWAY_ENVIRONMENT") == "production":
        return "production"

    # Default to local development
    return "local"


def load_credentials_from_env(env_var_name: str) -> str | None:
    """
    Load credentials from environment variable as JSON string.

    Args:
        env_var_name: Name of environment variable containing JSON credentials

    Returns:
        Path to temporary credentials file, or None if not found
    """
    env_json = os.getenv(env_var_name)
    if not env_json:
        return None

    try:
        credentials_data = json.loads(env_json)
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as temp_file:
            json.dump(credentials_data, temp_file)
            logger.info(f"Loaded credentials from environment variable: {env_var_name}")
            return temp_file.name
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Error parsing {env_var_name}: {e}")
        return None


def load_credentials_from_file(file_path: str) -> str | None:
    """
    Load credentials from file path.

    Args:
        file_path: Path to credentials file

    Returns:
        Absolute path to credentials file, or None if not found
    """
    path = Path(file_path)
    if path.exists():
        logger.info(f"Loaded credentials from file: {file_path}")
        return str(path)

    logger.warning(f"Credentials file not found: {file_path}")
    return None


# Initialize logging
logger = setup_logging()

# Load configuration based on environment
environment = get_environment()
logger.info(f"Detected environment: {environment}")

# Load settings from TOML files
_settings = Dynaconf(
    envvar_prefix="LANGTUT",
    settings_files=["settings.toml", ".secrets.toml"],
    environments=True,
    env=environment,
    load_dotenv=True,
)


class Config(BaseSettings):
    """
    Unified configuration using Pydantic.

    Single source of truth for all application settings with environment-aware
    configuration and simplified credential handling.

    Credentials are loaded with priority:
    1. Environment variable (JSON string for Railway)
    2. File path (for local development)
    """

    # Environment
    environment: str = environment
    debug: bool = _settings["debug"]

    # Core app
    secret_key: str | None = _settings.get("SECRET_KEY", None)
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
    client_secrets_file: str = _settings["client_secrets_file"]
    scopes: list[str] = _settings["scopes"]
    api_service_name: str = _settings["api_service_name"]
    api_version: str = _settings["api_version"]

    # Google TTS
    tts_enabled: bool = _settings["tts_enabled"]
    tts_language_code: str = _settings["tts_language_code"]
    tts_voice_name: str = _settings["tts_voice_name"]
    tts_audio_encoding: str = _settings["tts_audio_encoding"]
    google_cloud_service_account_file: str = _settings["google_cloud_service_account_file"]
    gcs_audio_bucket: str = _settings["gcs_audio_bucket"]

    # Private cached credentials
    _client_secrets_file_cache: str | None = None
    _google_cloud_service_account_file_cache: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def client_secrets_file_path(self) -> str | None:
        """
        Get OAuth client secrets file path.

        Priority:
        1. LANGTUT_CLIENT_SECRETS_JSON env var (JSON string)
        2. client_secrets_file path from settings
        """
        # Return cached value if available
        if self._client_secrets_file_cache is not None:
            return self._client_secrets_file_cache

        # Try environment variable first (Railway/production)
        result = load_credentials_from_env("LANGTUT_CLIENT_SECRETS_JSON")
        if result:
            self._client_secrets_file_cache = result
            return result

        # Try file path (local development)
        result = load_credentials_from_file(self.client_secrets_file)
        self._client_secrets_file_cache = result
        return result

    @computed_field  # type: ignore[prop-decorator]
    @property
    def google_cloud_service_account_file_path(self) -> str | None:
        """
        Get Google Cloud service account credentials file path.

        Priority:
        1. LANGTUT_GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON env var (JSON string)
        2. google_cloud_service_account_file path from settings
        """
        # Return cached value if available
        if self._google_cloud_service_account_file_cache is not None:
            return self._google_cloud_service_account_file_cache

        # Try environment variable first (Railway/production)
        result = load_credentials_from_env("LANGTUT_GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON")
        if result:
            self._google_cloud_service_account_file_cache = result
            return result

        # Try file path (local development)
        result = load_credentials_from_file(self.google_cloud_service_account_file)
        self._google_cloud_service_account_file_cache = result
        return result


# Export single config object
config = Config()

# Log configuration status
logger.info(f"Configuration loaded for {environment} environment")
logger.info(f"Debug mode: {config.debug}")
logger.info(f"Database path: {config.database_path}")
logger.info(f"TTS enabled: {config.tts_enabled}")
logger.info(f"OAuth credentials available: {config.client_secrets_file_path is not None}")
logger.info(
    f"TTS credentials available: {config.google_cloud_service_account_file_path is not None}"
)
