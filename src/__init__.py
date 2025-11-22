"""
Flask application factory for Language Learning Flashcard App.

Provides clean, modular initialization with focused functions for each
aspect of application setup.
"""

import os

from flask import Flask

from flask_session import Session
from src.config import config
from src.request_logger import setup_request_logging
from src.routes import register_blueprints
from src.utils import ensure_utf8_encoding


def configure_app(app: Flask) -> None:
    """Configure Flask application with settings from unified config.

    Args:
        app: Flask application instance
    """
    # Core app configuration
    app.secret_key = config.secret_key or os.urandom(24)
    app.config["DEBUG"] = config.debug

    # Session configuration
    app.config["SESSION_TYPE"] = config.session_type
    app.config["SESSION_PERMANENT"] = config.session_permanent
    app.config["SESSION_USE_SIGNER"] = config.session_use_signer
    app.config["SESSION_COOKIE_SECURE"] = config.session_cookie_secure
    app.config["SESSION_COOKIE_HTTPONLY"] = config.session_cookie_httponly
    app.config["SESSION_COOKIE_SAMESITE"] = config.session_cookie_samesite

    # JSON configuration
    app.config["JSON_AS_ASCII"] = config.json_as_ascii


def initialize_extensions(app: Flask) -> None:
    """Initialize Flask extensions.

    Args:
        app: Flask application instance
    """
    # Initialize Flask-Session
    Session(app)


def setup_middleware(app: Flask) -> None:
    """Setup middleware and request/response hooks.

    Args:
        app: Flask application instance
    """
    # Set up request/response logging
    setup_request_logging(app)


def create_app() -> Flask:
    """Application factory function.

    Creates and configures the Flask application with all necessary
    components properly initialized.

    Returns:
        Flask: Configured Flask application instance
    """
    # Set default encoding to UTF-8
    ensure_utf8_encoding()

    # Create Flask app with template and static folders
    app = Flask(__name__, template_folder="../templates", static_folder="../static")

    # Configure application settings
    configure_app(app)

    # Initialize extensions
    initialize_extensions(app)

    # Setup middleware
    setup_middleware(app)

    # Register blueprints
    register_blueprints(app)

    return app
