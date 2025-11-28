"""
Language Tutor Application

This is the main entry point for the application.
Optimized for Gunicorn deployment in all environments.

Development: uv run gunicorn --bind 0.0.0.0:8080 --workers 1 --reload run:app
Production:  Uses Railway's automatic Gunicorn deployment
"""

import os
from pathlib import Path

from app import create_app
from app.config import Environment, config, logger
from app.database import ensure_tables, init_database

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

# Ensure all tables exist
logger.info("Ensuring database tables exist...")
with app.app_context():
    ensure_tables()
logger.info("Database tables ready")

# Development-specific setup
if config.environment == Environment.LOCAL:
    # Enable insecure transport for local OAuth development
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    logger.info("OAuth insecure transport enabled for local development")
    logger.warning("⚠️  IMPORTANT: Do not use this in production!")

# Direct execution support (for debugging only)
if __name__ == "__main__":
    logger.warning("🐛 Running Flask development server directly (debugging mode)")
    logger.warning("⚠️  For production, use: uv run gunicorn --bind 0.0.0.0:8080 app:app")
    app.run(host="0.0.0.0", port=8080, debug=True)
