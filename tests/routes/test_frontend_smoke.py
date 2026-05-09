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
            ['{% extends "base.html" %}', "js/tts.js", "js/listening.js", "js/index.js"],
        ),
        ("card.html", ['{% extends "base.html" %}', "window.cardContext", "js/card.js"]),
        ("feedback.html", ['{% extends "base.html" %}', 'id="card-data"', "js/feedback.js"]),
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
    assert "caches.match('/offline.html')" in text
    assert "/static/css/style.css" in text
    assert "/static/js/mobile.js" in text
