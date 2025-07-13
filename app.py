"""
Language Tutor Application

This is the main entry point for the application.
Optimized for Gunicorn deployment in all environments.

Development: poetry run gunicorn --bind 0.0.0.0:8080 --workers 1 --reload app:app
Production:  Uses Railway's automatic Gunicorn deployment
"""

import os
from pathlib import Path

from src import create_app
from src.config import config, logger
from src.database import init_database

# Log startup information
logger.info('=== LANGUAGE TUTOR STARTUP ===')
logger.info(f'Python working directory: {Path.cwd()}')
logger.info(f'Environment: {config.ENVIRONMENT}')
logger.info(f'Debug mode: {config.DEBUG}')

# Create the app instance for Gunicorn
logger.info('Creating Flask application instance...')
app = create_app()

# Initialize database
logger.info('Initializing database...')
init_database(app)
logger.info('✅ Database initialization completed')

# Development-specific setup
if config.ENVIRONMENT == 'local':
    # Enable insecure transport for local OAuth development
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    logger.info('OAuth insecure transport enabled for local development')
    logger.warning('⚠️  IMPORTANT: Do not use this in production!')

# Validate configuration
if config.CLIENT_SECRETS_FILE:
    logger.info('✅ Client secrets configured - OAuth authentication available')
else:
    logger.warning('⚠️  WARNING: No client secrets configured. OAuth authentication will not work.')
    logger.warning(
        'Set LANGTUT_CLIENT_SECRETS_JSON environment variable or provide client_secret.json file.'
    )

# Log configuration status
logger.info(f'TTS enabled: {config.TTS_ENABLED}')
logger.info(f'Database path: {config.DATABASE_PATH}')
logger.info(f'Spreadsheet ID configured: {bool(config.SPREADSHEET_ID)}')
logger.info('✅ Application startup completed')

# Application ready for Gunicorn
logger.info(f'🚀 Application ready for Gunicorn in {config.ENVIRONMENT} mode')
