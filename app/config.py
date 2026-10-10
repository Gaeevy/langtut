"""
Unified configuration management for Language Learning Flashcard App.

Single source of truth for all configuration with environment-aware settings
and simplified credential handling (env vars first, then file paths).
"""

import os
from enum import StrEnum
from pathlib import Path

from dynaconf import Dynaconf
from pydantic import BaseModel, ConfigDict, Field

from app.logging import setup_logging
from app.mcp_settings import MCPSettings
from app.utils import resolve_secrets_file_path


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


def optional_credentials(json_key: str, file_key: str) -> str | None:
    """Resolve configured credentials; standalone tools need no Google credentials."""
    payload, path = _settings.get(json_key), _settings.get(file_key)
    return resolve_secrets_file_path(payload, path) if payload or path else None


_client_secrets_file_path = optional_credentials("client_secrets_json", "client_secrets_file")
_google_cloud_service_account_file_path = optional_credentials(
    "google_cloud_service_account_json", "google_cloud_service_account_file"
)


class Config(BaseModel):
    """Unified configuration using Pydantic.

    Single source of truth for all application settings with environment-aware
    configuration and simplified credential handling.

    Credentials are loaded with priority:
    1. Environment variable (JSON string for Railway)
    2. File path (for local development)
    """

    model_config = ConfigDict(validate_default=True)

    # Environment
    environment: Environment = _environment
    debug: bool = _settings["debug"]

    # Core app
    secret_key: str | None = _settings.get("SECRET_KEY")
    max_cards_per_session: int = _settings["max_cards_per_session"]
    spreadsheet_id: str = _settings["spreadsheet_id"]
    verbs_import_api_key: str = _settings.get("verbs_import_api_key", "")
    verbs_import_local_url: str = _settings.get("verbs_import_local_url", "http://127.0.0.1:8080")
    verbs_import_production_url: str = _settings.get("verbs_import_production_url", "")

    # Database
    database_path: str = _settings["database_path"]

    # Shared web/MCP runtime; Dynaconf is the only environment loader.
    bind_host: str = _settings["bind_host"]
    port: int = Field(default=_settings.get("port", os.getenv("PORT", 8080)), ge=1, le=65535)
    allowed_hosts: list[str] = _settings["allowed_hosts"]
    proxy_trusted_ips: list[str] = _settings["proxy_trusted_ips"]
    mcp_enabled: bool = _settings["mcp_enabled"]
    mcp_allowed_origins: list[str] = _settings["mcp_allowed_origins"]
    mcp_requests_per_minute: int = Field(
        default=_settings["mcp_requests_per_minute"], ge=1, le=10000
    )

    def mcp_settings(self) -> MCPSettings:
        """Pass resolved shared values to MCP without reading configuration again."""
        return MCPSettings(
            enabled=self.mcp_enabled,
            database_path=Path(self.database_path),
            allowed_hosts=[value for host in self.allowed_hosts for value in (host, f"{host}:*")],
            allowed_origins=self.mcp_allowed_origins,
            requests_per_minute=self.mcp_requests_per_minute,
        )

    # Flask Session
    session_type: str = _settings["session_type"]
    session_permanent: bool = _settings["session_permanent"]
    session_use_signer: bool = _settings["session_use_signer"]
    session_refresh_each_request: bool = _settings.get("session_refresh_each_request", False)
    session_file_dir: str = _settings["session_file_dir"]
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
    tts_audio_encoding: str = _settings["tts_audio_encoding"]
    gcs_audio_bucket: str = _settings["gcs_audio_bucket"]

    # Credentials
    client_secrets_file_path: str | None = _client_secrets_file_path
    google_cloud_service_account_file_path: str | None = _google_cloud_service_account_file_path

    # Encryption
    encryption_key: str = _settings.get("ENCRYPTION_KEY", "")


# Export single config object
config = Config()
