"""
Routes package for the Language Learning Flashcard App.

This package contains all the route blueprints organized by feature.
"""

from flask import Flask

from .admin import admin_bp
from .api import api_bp
from .auth import auth_bp
from .flashcard import flashcard_bp
from .index import index_bp
from .learn import learn_bp
from .settings import settings_bp
from .test import test_bp


def register_blueprints(app: Flask) -> None:
    """Register all blueprints with the Flask app."""
    app.register_blueprint(auth_bp)
    app.register_blueprint(index_bp)  # New: Homepage routes
    app.register_blueprint(learn_bp)  # New: Learn mode routes
    app.register_blueprint(flashcard_bp)  # Legacy: kept for backward compatibility
    app.register_blueprint(settings_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(test_bp)
