"""Guardrail tests for Flask session configuration.

Production runs Gunicorn with multiple workers, so the session backend MUST
be shared between workers (filesystem on a persistent volume). An in-memory
backend like ``cachelib`` with ``SimpleCache`` would silently regress to
per-worker state, so we pin the intended config here.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flask import Flask

from app import configure_app, create_app
from app.config import config


def test_default_session_type_is_filesystem() -> None:
    """Session type must default to a backend shared across Gunicorn workers."""
    assert config.session_type == "filesystem", (
        "Default session_type must remain 'filesystem' (or another shared backend "
        "like 'sqlalchemy'/'redis'). In-process backends such as 'cachelib' "
        "break multi-worker deployments."
    )


def test_session_file_dir_is_configured() -> None:
    """Filesystem sessions require an explicit, non-empty session_file_dir."""
    assert config.session_type != "filesystem" or config.session_file_dir, (
        "session_file_dir must be set when session_type='filesystem' so all "
        "Gunicorn workers share the same session store."
    )


def test_session_refresh_each_request_defaults_to_false() -> None:
    """Read-only requests must not overwrite newer shared session snapshots."""
    assert config.session_refresh_each_request is False


def test_configure_app_sets_filesystem_session_dir(tmp_path, monkeypatch) -> None:
    """configure_app wires SESSION_FILE_DIR and creates the directory."""
    target_dir = tmp_path / "flask_session"
    monkeypatch.setattr(config, "session_type", "filesystem")
    monkeypatch.setattr(config, "session_file_dir", str(target_dir))
    monkeypatch.setattr(config, "session_refresh_each_request", False)

    app = Flask(__name__)
    configure_app(app)

    assert app.config["SESSION_TYPE"] == "filesystem"
    assert app.config["SESSION_USE_SIGNER"] is True
    assert app.config["SESSION_REFRESH_EACH_REQUEST"] is config.session_refresh_each_request
    assert Path(app.config["SESSION_FILE_DIR"]) == target_dir.resolve()
    assert target_dir.is_dir(), "Session directory must be created eagerly"


def test_configure_app_uses_session_refresh_setting(monkeypatch) -> None:
    """The Flask setting follows the typed application configuration."""
    monkeypatch.setattr(config, "session_refresh_each_request", True)

    app = Flask(__name__)
    configure_app(app)

    assert app.config["SESSION_REFRESH_EACH_REQUEST"] is True


def test_create_app_uses_shared_filesystem_session_interface(tmp_path, monkeypatch) -> None:
    """create_app produces a Flask app backed by FileSystemSessionInterface."""
    monkeypatch.setattr(config, "session_type", "filesystem")
    monkeypatch.setattr(config, "session_file_dir", str(tmp_path / "sessions"))

    app = create_app()

    interface_name = type(app.session_interface).__name__
    assert interface_name == "FileSystemSessionInterface", (
        f"Expected FileSystemSessionInterface, got {interface_name}. "
        "A non-shared backend would regress multi-worker production sessions."
    )


@pytest.mark.parametrize("bad_type", ["cachelib", "null"])
def test_known_unshared_session_types_are_not_default(bad_type: str) -> None:
    """Catch regressions where session_type defaults to an unshared backend."""
    assert config.session_type != bad_type, (
        f"session_type must not default to '{bad_type}': it is not shared across Gunicorn workers."
    )
