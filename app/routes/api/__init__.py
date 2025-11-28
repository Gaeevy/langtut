"""
API routes package for the Language Learning Flashcard App.

This package organizes API endpoints into logical modules:
- tts.py: Text-to-speech endpoints
- cards.py: Card data endpoints for listening mode
- language.py: Language settings management
"""

from flask import Blueprint

from .cards import cards_bp
from .language import language_bp
from .tts import tts_bp

# Create main API blueprint
api_bp = Blueprint("api", __name__, url_prefix="/api")


def register_api_blueprints(app):
    """Register all API sub-blueprints.

    Called automatically when api_bp is registered with the app.
    """
    # Register nested blueprints under /api/
    api_bp.register_blueprint(tts_bp)
    api_bp.register_blueprint(cards_bp)
    api_bp.register_blueprint(language_bp)


# Auto-register sub-blueprints when this module is imported
register_api_blueprints(None)  # Pass None since we register with api_bp, not app

__all__ = ["api_bp", "cards_bp", "language_bp", "tts_bp"]
