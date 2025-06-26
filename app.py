"""
Language Tutor Application

This is the main entry point for the application.
"""

import os
from pathlib import Path

from src import create_app
from src.config import CLIENT_SECRETS_FILE, FLASK_DEBUG, logger, settings
from src.database import init_database

# Log startup information
logger.info('=== LANGUAGE TUTOR STARTUP ===')
logger.info(f'Python working directory: {Path.cwd()}')
logger.info(f'Flask debug mode: {FLASK_DEBUG}')
logger.info(f'Environment: {os.getenv("ENVIRONMENT", "unknown")}')

# Create the app instance for Gunicorn
logger.info('Creating Flask application instance...')
app = create_app()

# Initialize database
logger.info('Initializing database...')
init_database(app)
logger.info('✅ Database initialization completed')

# Database tables will be created automatically when first accessed

if __name__ == '__main__':
    # Determine if we're in development or production
    # Default to development when running python app.py directly
    is_development = (
        os.getenv('FLASK_ENV') == 'development'
        or os.getenv('ENVIRONMENT') == 'development'
        or FLASK_DEBUG  # Use the FLASK_DEBUG setting from config
        or not os.getenv('PORT')  # If no PORT env var, assume development
    )

    # Add development setup
    if is_development:
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
        logger.info('OAuth insecure transport enabled for local development')
        logger.warning('⚠️  IMPORTANT: Do not use this in production!')

        # Check if the client secrets file exists (only relevant in development)
        if not Path(CLIENT_SECRETS_FILE).exists():
            logger.warning(f'Client secrets file not found: {CLIENT_SECRETS_FILE}')
            logger.warning('OAuth authentication will not work without client secrets')
            logger.info('See README.md for setup instructions')

    if is_development:
        logger.info('🚀 Starting in DEVELOPMENT mode')
        logger.info('   - Debug mode enabled')
        logger.info('   - Auto-reload enabled')
        logger.info('   - Server: http://127.0.0.1:8080')
        app.run(debug=True, port=8080)
    else:
        # Production mode (Railway, Heroku, etc.)
        port = int(os.environ.get('PORT', 5000))
        logger.info('🚀 Starting in PRODUCTION mode')
        logger.info(f'   - Port: {port}')
        logger.info('   - Debug mode disabled')
        logger.info('   - Host: 0.0.0.0')
        app.run(host='0.0.0.0', port=port, debug=False)  # nosec B104
else:
    # Production mode (running with Gunicorn)
    logger.info('🚀 Running in PRODUCTION mode (Gunicorn)')

    # Check if we have client secrets configured (via env var or file)
    has_client_secrets = (
        settings.get('CLIENT_SECRETS_JSON') is not None or Path(CLIENT_SECRETS_FILE).exists()
    )

    if has_client_secrets:
        logger.info('✅ Client secrets configured - OAuth authentication available')
    else:
        logger.warning(
            '⚠️  WARNING: No client secrets configured. OAuth authentication will not work.'
        )
        logger.warning(
            'Set LANGTUT_CLIENT_SECRETS_JSON environment variable or provide client_secret.json file.'
        )

    # Log configuration status
    logger.info(f'TTS enabled: {settings.get("TTS_ENABLED", False)}')
    logger.info(f'Spreadsheet ID configured: {bool(settings.get("SPREADSHEET_ID"))}')
    logger.info('✅ Application startup completed')
