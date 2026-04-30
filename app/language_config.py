"""Language codes for settings UI: TTS-capable codes plus common L1 options."""

from __future__ import annotations

from pathlib import Path

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_LANGUAGES_YAML = _PROJECT_ROOT / "config" / "languages.yaml"

# Labels for codes offered in settings selects (target is TTS-backed; others for columns/UI)
LANGUAGE_LABELS: dict[str, str] = {
    "de": "German (Deutsch)",
    "en": "English",
    "es": "Spanish (Español)",
    "fr": "French (Français)",
    "it": "Italian (Italiano)",
    "pt": "Portuguese (Português)",
    "ru": "Russian (Русский)",
}

# Extras users may choose for native/hint columns beyond what TTS lists in yaml
_EXTRA_UI_CODES = frozenset({"ru", "es", "fr", "de", "it"})


def _load_yaml_language_codes() -> list[str]:
    """Return language keys from config/languages.yaml under top-level ``languages``."""
    with _LANGUAGES_YAML.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    langs = data.get("languages") or {}
    return sorted(langs.keys())


def get_ui_language_codes() -> list[str]:
    """Return sorted list of language codes available in spreadsheet settings selects.

    Union of TTS-configured languages and a small set of common non-TTS UI codes.
    """
    codes = set(_load_yaml_language_codes()) | set(_EXTRA_UI_CODES)
    return sorted(codes)


def label_for_code(code: str) -> str:
    """Human label for a language code, falling back to the code itself."""
    return LANGUAGE_LABELS.get(code, code.upper())
