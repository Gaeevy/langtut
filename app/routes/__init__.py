"""
Routes package for the Language Learning Flashcard App.

This package contains all the route blueprints organized by feature:
- index: Homepage (/)
- learn: Learn mode (/learn/*)
- review: Review mode (/review/*)
- settings: User settings (/settings/*)
- api/: API endpoints (/api/tts/*, /api/cards/*, /api/language-settings/*)
- admin: Database administration (/admin/*)
- auth: OAuth authentication (/auth/*, /oauth2callback)
- test: Development testing (/test/*)
"""

from flask import Flask

from .admin import admin_bp
from .api import api_bp
from .auth import auth_bp
from .index import index_bp
from .learn import learn_bp
from .review import review_bp
from .settings import settings_bp
from .test import test_bp


def register_blueprints(app: Flask) -> None:
    """Register all blueprints with the Flask app."""
    app.register_blueprint(auth_bp)
    app.register_blueprint(index_bp)  # Homepage routes
    app.register_blueprint(learn_bp)  # Learn mode routes
    app.register_blueprint(review_bp)  # Review mode routes
    app.register_blueprint(settings_bp)  # Settings routes
    app.register_blueprint(api_bp)  # API routes
    app.register_blueprint(admin_bp)  # Admin routes
    app.register_blueprint(test_bp)  # Test routes
