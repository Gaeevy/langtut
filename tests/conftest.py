"""Pytest configuration and fixtures for the test suite."""

import pytest
from flask import Flask

from app.config import config
from app.models import Card, Levels
from app.routes import register_blueprints
from app.services.google_oauth import GoogleOAuthService


@pytest.fixture
def google_client_config() -> dict:
    """Provide synthetic Google client settings."""
    return {
        "web": {
            "client_id": "test-client",
            "client_secret": "test-secret",
            "auth_uri": "https://accounts.example.test/authorize",
            "token_uri": "https://accounts.example.test/token",
        }
    }


@pytest.fixture
def google_oauth(google_client_config) -> GoogleOAuthService:
    return GoogleOAuthService(
        google_client_config, config.google_identity_scopes, config.google_sheets_scopes
    )


@pytest.fixture
def app(google_oauth):
    """Create a Flask application for testing."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    app.extensions["google_oauth"] = google_oauth

    register_blueprints(app)

    return app


@pytest.fixture
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()


@pytest.fixture
def app_context(app):
    """Create an application context for testing."""
    with app.app_context():
        yield


@pytest.fixture
def request_context(app):
    """Create a request context for testing session-dependent code."""
    with app.test_request_context():
        yield


def make_card(
    id: int = 1,
    word: str = "olá",
    translation: str = "hello",
    level: Levels = Levels.LEVEL_0,
    cnt_shown: int = 0,
    cnt_corr_answers: int = 0,
    equivalent: str = "",
    example: str = "Olá, como vai?",
    example_translation: str = "Hello, how are you?",
) -> Card:
    """Create a Card with sensible defaults for testing."""
    return Card(
        id=id,
        word=word,
        translation=translation,
        equivalent=equivalent,
        example=example,
        example_translation=example_translation,
        cnt_shown=cnt_shown,
        cnt_corr_answers=cnt_corr_answers,
        level=level,
    )


@pytest.fixture
def sample_card():
    """Create a sample card for testing."""
    return make_card()


@pytest.fixture
def sample_cards():
    """Create a list of sample cards for testing."""
    return [
        make_card(id=1, word="olá", translation="hello"),
        make_card(id=2, word="obrigado", translation="thank you"),
        make_card(id=3, word="adeus", translation="goodbye"),
    ]
