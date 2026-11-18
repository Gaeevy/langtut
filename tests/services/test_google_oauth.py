"""Verify Google OAuth configuration is loaded only at application setup."""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from oauthlib.oauth2 import MismatchingStateError
from pydantic import SecretStr

from app import create_app
from app.config import config


def test_oauth_library_compares_recorded_state_before_token_exchange(google_oauth, monkeypatch):
    _, transaction = google_oauth.start_login(
        "https://example.test/oauth2callback", expires_at=2_000_000_000
    )
    request = Mock()
    monkeypatch.setattr("requests_oauthlib.OAuth2Session.request", request)
    with pytest.raises(MismatchingStateError):
        google_oauth.complete_authorization(
            "https://example.test/oauth2callback?code=synthetic&state=wrong", transaction
        )
    request.assert_not_called()


@pytest.mark.parametrize("source", ["file", "inline-json"])
def test_application_loads_google_oauth_configuration(
    tmp_path, monkeypatch, google_client_config, source
):
    client_file = tmp_path / "client.json"
    payload = json.dumps(google_client_config)
    inline_json = None
    if source == "file":
        client_file.write_text(payload)
    else:
        inline_json = SecretStr(payload)
    monkeypatch.setattr(config, "client_secrets_json", inline_json)
    monkeypatch.setattr(config, "client_secrets_file", str(client_file))
    monkeypatch.setattr(config, "session_file_dir", str(tmp_path / "sessions"))

    app = create_app()
    oauth = app.extensions["google_oauth"]

    assert oauth.client_id == google_client_config["web"]["client_id"]
    assert oauth.client_secret not in repr(oauth)
    assert oauth.client_secret not in repr(config.client_secrets_json)


def test_application_rejects_incomplete_google_client_configuration(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "session_file_dir", str(tmp_path / "sessions"))
    monkeypatch.setattr(
        config, "client_secrets_json", SecretStr('{"web":{"client_id":"incomplete"}}')
    )

    with pytest.raises(ValueError, match="Invalid Google OAuth client configuration"):
        create_app()


def test_import_does_not_load_google_oauth_client_file(tmp_path):
    invalid_file = tmp_path / "client.json"
    invalid_file.write_text("invalid JSON")
    root = Path(__file__).resolve().parents[2]
    (tmp_path / "settings.toml").write_text((root / "settings.toml").read_text())
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("LANGTUT_", "RAILWAY_", "DYNACONF_"))
    }
    env.update(
        PYTHONPATH=str(root),
        LANGTUT_CLIENT_SECRETS_FILE=str(invalid_file),
        LANGTUT_TTS_ENABLED="false",
    )
    code = """
import os
import sys

def reject_client_file_read(event, args):
    if event == "open" and args[0] == os.environ["LANGTUT_CLIENT_SECRETS_FILE"]:
        raise AssertionError("Google OAuth client file read during import")

sys.addaudithook(reject_client_file_read)
import app.config
import app.services.auth_manager
import app.services.google_oauth
"""
    subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=env, check=True)
