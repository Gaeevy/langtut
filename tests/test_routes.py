"""Tests for route registration and basic route functionality."""


class TestRouteRegistration:
    """Tests for verifying all routes are registered correctly."""

    def test_app_creates_successfully(self, app):
        """Application should create without errors."""
        assert app is not None

    def test_routes_registered(self, app):
        """All expected routes should be registered."""
        routes = [rule.rule for rule in app.url_map.iter_rules()]

        # Homepage
        assert "/" in routes

        # Learn mode routes
        assert "/learn/card" in routes
        assert "/learn/answer" in routes
        assert "/learn/feedback/<correct>" in routes
        assert "/learn/next" in routes
        assert "/learn/results" in routes
        assert "/learn/start/<tab_name>" in routes

        # Review mode routes
        assert "/review/card" in routes
        assert "/review/flip" in routes
        assert "/review/start/<tab_name>" in routes
        assert "/review/nav/<direction>" in routes

        # API routes
        assert "/api/tts/status" in routes
        assert "/api/tts/speak" in routes
        assert "/api/cards/<tab_name>" in routes
        assert "/api/language-settings" in routes

    def test_no_legacy_flashcard_routes(self, app):
        """Legacy flashcard routes should not be registered."""
        routes = [rule.rule for rule in app.url_map.iter_rules()]

        # These were legacy routes that should no longer exist
        assert "/start/<tab_name>" not in routes
        assert "/card/<mode>" not in routes
        assert "/feedback/<correct>/<mode>" not in routes


class TestHomepage:
    """Tests for the homepage route."""

    def test_homepage_route_exists(self, app):
        """Homepage route should be registered."""
        routes = [rule.rule for rule in app.url_map.iter_rules()]
        assert "/" in routes


class TestTTSRoutes:
    """Tests for TTS API routes."""

    def test_tts_status_returns_json(self, client):
        """TTS status should return JSON."""
        response = client.get("/api/tts/status")
        assert response.status_code == 200
        assert response.content_type == "application/json"

        data = response.get_json()
        assert "available" in data

    def test_tts_speak_requires_text(self, client):
        """TTS speak should require text parameter."""
        response = client.post("/api/tts/speak", json={})
        assert response.status_code == 400

        data = response.get_json()
        assert data["success"] is False
        assert "Text is required" in data["error"]

    def test_tts_speak_rejects_empty_text(self, client):
        """TTS speak should reject empty text."""
        response = client.post("/api/tts/speak", json={"text": "   "})
        assert response.status_code == 400

        data = response.get_json()
        assert data["success"] is False


class TestLanguageSettingsRoutes:
    """Tests for language settings API routes."""

    def test_validate_requires_json_body(self, client):
        """Validate endpoint should require JSON body."""
        response = client.post(
            "/api/language-settings/validate",
            data="not json",
            content_type="application/json",
        )
        # Returns error status (400 or 500) because JSON parsing fails
        assert response.status_code in [400, 500]

    def test_validate_requires_language_settings(self, client):
        """Validate endpoint should require language_settings field."""
        response = client.post(
            "/api/language-settings/validate",
            json={},
            content_type="application/json",
        )
        assert response.status_code == 400

        data = response.get_json()
        # Check for any error about missing settings
        assert "required" in data["error"].lower() or "settings" in data["error"].lower()

    def test_validate_valid_settings(self, client):
        """Validate should accept valid language settings."""
        response = client.post(
            "/api/language-settings/validate",
            json={"language_settings": {"original": "ru", "target": "pt", "hint": "en"}},
            content_type="application/json",
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["success"] is True
        assert data["valid"] is True
