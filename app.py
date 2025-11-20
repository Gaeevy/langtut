"""
Language Tutor Application

This is the main entry point for the application.
Optimized for Gunicorn deployment in all environments.

Development: uv run gunicorn --bind 0.0.0.0:8080 --workers 1 --reload app:app
Production:  Uses Railway's automatic Gunicorn deployment
"""

import os
from pathlib import Path

from src import create_app
from src.config import config, logger
from src.database import init_database

# Log startup information
logger.info("=== LANGUAGE TUTOR STARTUP ===")
logger.info(f"Python working directory: {Path.cwd()}")
logger.info(f"Environment: {config.environment}")
logger.info(f"Debug mode: {config.debug}")

# Create the app instance for Gunicorn
logger.info("Creating Flask application instance...")
app = create_app()

# Initialize database
logger.info("Initializing database...")
init_database(app)
logger.info("✅ Database initialization completed")

# Development-specific setup
if config.environment == "local":
    # Enable insecure transport for local OAuth development
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    logger.info("OAuth insecure transport enabled for local development")
    logger.warning("⚠️  IMPORTANT: Do not use this in production!")

# Validate configuration
if config.client_secrets_file_path:
    logger.info("✅ Client secrets configured - OAuth authentication available")
else:
    logger.warning("⚠️  WARNING: No client secrets configured. OAuth authentication will not work.")
    logger.warning(
        "Set LANGTUT_CLIENT_SECRETS_JSON environment variable or provide client_secret.json file."
    )

# Log configuration status
logger.info(f"TTS enabled: {config.tts_enabled}")
logger.info(f"Database path: {config.database_path}")
logger.info(f"Spreadsheet ID configured: {bool(config.spreadsheet_id)}")
logger.info("✅ Application startup completed")

# Application ready for Gunicorn
logger.info(f"🚀 Application ready for Gunicorn in {config.environment} mode")

# Direct execution support (for debugging only)
if __name__ == "__main__":
    logger.warning("🐛 Running Flask development server directly (debugging mode)")
    logger.warning("⚠️  For production, use: uv run gunicorn --bind 0.0.0.0:8080 app:app")
    app.run(host="0.0.0.0", port=8080, debug=True)
