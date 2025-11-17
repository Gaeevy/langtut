"""
Unified configuration management for Language Learning Flashcard App.

Single source of truth for all configuration with environment-aware settings
and dual credential handling (local files vs production environment variables).
"""

import json
import logging
import os
import sys
import tempfile
from pathlib import Path

from dynaconf import Dynaconf


def setup_logging():
    """Configure logging for both local development and Railway deployment."""
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create formatter with milliseconds for performance debugging
    formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    # Console handler (works on both local and Railway)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Set specific logger levels
    logging.getLogger('werkzeug').setLevel(logging.WARNING)  # Reduce Flask request noise
    logging.getLogger('googleapiclient.discovery').setLevel(
        logging.WARNING
    )  # Reduce Google API noise

    return logger


def get_environment() -> str:
    """
    Environment detection using Railway's automatic variables.

    Returns:
        str: 'testing', 'production', or 'local'
    """
    # Testing environment
    if (
        os.getenv('PYTEST_CURRENT_TEST') is not None
        or os.getenv('ENVIRONMENT') == 'testing'
        or 'pytest' in sys.modules
    ):
        return 'testing'

    # Production environment - Railway sets RAILWAY_ENVIRONMENT automatically
    if os.getenv('RAILWAY_ENVIRONMENT') == 'production':
        return 'production'

    # Default to local development
    return 'local'


def get_credentials_file(
    settings_obj, setting_key: str, env_var_key: str, default_file: str
) -> str | None:
    """
    Get credentials file path with dual handling:
    - Local: Use file from settings
    - Production: Create temp file from environment variable

    Args:
        settings_obj: Dynaconf settings object
        setting_key: Key in settings.toml for local file path
        env_var_key: Environment variable key for production JSON
        default_file: Default file name if setting not found

    Returns:
        str: Path to credentials file, or None if not available
    """
    # Check for environment variable (production)
    env_var_content = settings_obj.get(env_var_key, None)

    if env_var_content:
        # Production: Create temporary file from env var
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
                if isinstance(env_var_content, str):
                    credentials_data = json.loads(env_var_content)
                else:
                    credentials_data = env_var_content

                json.dump(credentials_data, temp_file)
                return temp_file.name
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f'Error parsing {env_var_key}: {e}')
            return None
    else:
        # Local: Use file from settings
        file_path = settings_obj.get(setting_key, default_file)
        if Path(file_path).exists():
            return file_path
        logger.warning(f'Credentials file not found: {file_path}')
        return None


# Initialize logging
logger = setup_logging()

# Load configuration based on environment
environment = get_environment()
logger.info(f'Detected environment: {environment}')

settings = Dynaconf(
    envvar_prefix='LANGTUT',
    settings_files=['settings.toml', '.secrets.toml'],
    environments=True,
    env=environment,
    load_dotenv=True,
)


class Config:
    """
    Unified configuration object.

    Single source of truth for all application settings with environment-aware
    configuration and dual credential handling.
    """

    # Environment
    ENVIRONMENT = environment
    DEBUG = settings.get('debug', False)

    # Core app
    SECRET_KEY = settings.get('SECRET_KEY', None)
    MAX_CARDS_PER_SESSION = settings.get('max_cards_per_session', 10)
    SPREADSHEET_ID = settings.get('spreadsheet_id')

    # Database
    DATABASE_PATH = settings.get('database_path')
    SQLALCHEMY_TRACK_MODIFICATIONS = settings.get('sqlalchemy_track_modifications', False)

    # Flask Session
    SESSION_TYPE = settings.get('session_type', 'filesystem')
    SESSION_PERMANENT = settings.get('session_permanent', False)
    SESSION_USE_SIGNER = settings.get('session_use_signer', True)
    SESSION_COOKIE_SECURE = settings.get('session_cookie_secure', False)
    SESSION_COOKIE_HTTPONLY = settings.get('session_cookie_httponly', True)
    SESSION_COOKIE_SAMESITE = settings.get('session_cookie_samesite', 'Lax')

    # Flask JSON
    JSON_AS_ASCII = settings.get('json_as_ascii', False)
    JSONIFY_MIMETYPE = settings.get('jsonify_mimetype', 'application/json; charset=utf-8')

    # Google OAuth - Dual credential handling
    CLIENT_SECRETS_FILE = get_credentials_file(
        settings, 'client_secrets_file', 'CLIENT_SECRETS_JSON', 'client_secret.json'
    )
    SCOPES = settings.get('scopes', [])
    API_SERVICE_NAME = settings.get('api_service_name', 'sheets')
    API_VERSION = settings.get('api_version', 'v4')

    # Google TTS - Dual credential handling
    TTS_ENABLED = settings.get('tts_enabled', True)
    TTS_LANGUAGE_CODE = settings.get('tts_language_code', 'pt-PT')
    TTS_VOICE_NAME = settings.get('tts_voice_name', 'pt-PT-Standard-A')
    TTS_AUDIO_ENCODING = settings.get('tts_audio_encoding', 'MP3')
    GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE = get_credentials_file(
        settings,
        'google_cloud_service_account_file',
        'GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON',
        'google-cloud-service-account.json',
    )
    GCS_AUDIO_BUCKET = settings.get('gcs_audio_bucket', 'langtut-tts')

    # Testing mocks
    TESTING_MOCK_OAUTH = (
        settings.get('mock.oauth_enabled', False) if environment == 'testing' else False
    )
    TESTING_MOCK_SHEETS = (
        settings.get('mock.sheets_enabled', False) if environment == 'testing' else False
    )


# Export single config object
config = Config()

# Log configuration status
logger.info(f'Configuration loaded for {environment} environment')
logger.info(f'Debug mode: {config.DEBUG}')
logger.info(f'Database path: {config.DATABASE_PATH}')
logger.info(f'TTS enabled: {config.TTS_ENABLED}')
logger.info(f'OAuth credentials available: {config.CLIENT_SECRETS_FILE is not None}')
logger.info(f'TTS credentials available: {config.GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE is not None}')
