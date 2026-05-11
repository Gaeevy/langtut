"""Frontend template and asset smoke tests."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "app" / "templates"
STATIC = ROOT / "app" / "static"


@pytest.mark.parametrize(
    ("template_name", "required_snippets"),
    [
        (
            "index.html",
            [
                '{% extends "base.html" %}',
                "js/tts.js",
                "js/listening.js",
                "js/index.js",
                'id="unlockAudioBtn"',
                'id="startListeningBtn"',
                'id="pauseResumeBtn"',
            ],
        ),
        (
            "card.html",
            [
                '{% extends "base.html" %}',
                "window.cardContext",
                "window.cardData",
                "js/tts.js",
                "js/card.js",
            ],
        ),
        (
            "feedback.html",
            ['{% extends "base.html" %}', 'id="card-data"', "js/tts.js", "js/feedback.js"],
        ),
    ],
)
def test_templates_include_expected_script_wiring(
    template_name: str, required_snippets: list[str]
) -> None:
    """Critical templates keep expected script/data wiring in place."""
    text = (TEMPLATES / template_name).read_text(encoding="utf-8")
    for snippet in required_snippets:
        assert snippet in text


def test_base_template_keeps_script_block_and_mobile_script() -> None:
    """Base template exposes extension script block and global mobile script include."""
    text = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    assert "{% block scripts %}{% endblock %}" in text
    assert "js/mobile.js" in text


def test_service_worker_offline_fallback_and_core_assets_are_declared() -> None:
    """Service worker keeps offline fallback and core assets in cache list."""
    text = (STATIC / "sw.js").read_text(encoding="utf-8")
    assert "caches.match('/static/offline.html')" in text
    assert "/static/offline.html" in text
    assert "/static/css/style.css" in text
    assert "/static/js/mobile.js" in text


def test_offline_fallback_file_exists() -> None:
    """Offline fallback file should exist as static asset."""
    assert (STATIC / "offline.html").exists()


def test_index_template_uses_bootstrap_icons_only_for_listening_controls() -> None:
    """Listening controls should use Bootstrap icon classes, not Font Awesome."""
    text = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    assert "bi bi-volume-up" in text
    assert "bi bi-play-fill" in text
    assert "fas fa-" not in text


_TTS_JS_REQUIRED_SYMBOLS = (
    "unlockAudio",
    "unlockChromeIOS",
    "unlockMobile",
    "speakCard",
    "fetchAudio",
    "playAudio",
    "waitForService",
    "resetAudioSystem",
    "clearCache",
    "getCacheStats",
    "ensureUnlockedFromGesture",
)


def test_tts_js_exports_public_api_for_callers() -> None:
    """TTSManager must keep methods used by card, feedback, and listening scripts."""
    text = (STATIC / "js" / "tts.js").read_text(encoding="utf-8")
    for name in _TTS_JS_REQUIRED_SYMBOLS:
        assert f"{name}(" in text or f" async {name}(" in text or f"{name} (" in text


_LISTENING_FORBIDDEN_SNIPPETS = (
    "unlockAudioContext",
    "unlockAudioForChromeIOS",
    "primedAudioForChromeIOS =",
    "audioUnlocked = true",
)


def test_listening_js_delegates_unlock_to_tts_manager() -> None:
    """Listening mode must not duplicate Chrome iOS priming or mutating ttsManager internals."""
    text = (STATIC / "js" / "listening.js").read_text(encoding="utf-8")
    for snippet in _LISTENING_FORBIDDEN_SNIPPETS:
        assert snippet not in text
