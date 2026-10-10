"""Shared environment configuration and ASGI proxy boundaries."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from flask import Flask, request
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app import configure_app
from app.config import config
from asgi import create_combined_app

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("environment", ["local", "production"])
def test_shared_settings_follow_environment_and_overrides(tmp_path, environment):
    (tmp_path / "settings.toml").write_text((ROOT / "settings.toml").read_text())
    (tmp_path / ".secrets.toml").write_text(
        f'[{environment}]\ndatabase_path="file-setting.db"\nmcp_enabled=false\n'
    )
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("LANGTUT_", "RAILWAY_", "DYNACONF_"))
    }
    env.update(
        {
            "PYTHONPATH": str(ROOT),
            "RAILWAY_ENVIRONMENT": environment,
            "LANGTUT_DATABASE_PATH": "override.db",
            "LANGTUT_MCP_ENABLED": "true",
            "LANGTUT_ALLOWED_HOSTS": '["demo.example.com"]',
            "PORT": "9876",
            "LANGTUT_MCP_REQUESTS_PER_MINUTE": "30",
        }
    )
    code = """
import json
from app.config import config
mcp = config.mcp_settings()
print(json.dumps(dict(database=config.database_path, mcp_database=str(mcp.database_path),
 enabled=mcp.enabled, hosts=mcp.allowed_hosts, port=config.port, bind=config.bind_host,
 origins=mcp.allowed_origins, limit=mcp.requests_per_minute)))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    values = json.loads(result.stdout.splitlines()[-1])
    assert values["database"] == values["mcp_database"] == "override.db"
    assert values["enabled"]
    assert values["hosts"] == ["demo.example.com", "demo.example.com:*"]
    assert values["port"] == 9876
    assert values["limit"] == 30
    # Only comparing configuration; this test never opens a listening socket.
    assert values["bind"] == ("127.0.0.1" if environment == "local" else "0.0.0.0")  # nosec B104
    assert bool(values["origins"]) == (environment == "local")


@pytest.mark.parametrize(("peer", "expected_scheme"), [("10.0.0.1", "https"), ("10.0.0.2", "http")])
def test_only_trusted_proxy_can_set_scheme_for_flask(monkeypatch, tmp_path, peer, expected_scheme):
    monkeypatch.setattr(config, "allowed_hosts", ["demo.example.com"])
    monkeypatch.setattr(config, "session_file_dir", str(tmp_path / "sessions"))
    web = Flask(__name__)
    configure_app(web)
    web.add_url_rule("/scheme", view_func=lambda: request.scheme)
    options = config.mcp_settings().model_copy(update={"enabled": False})
    app = ProxyHeadersMiddleware(create_combined_app(web, options), trusted_hosts=["10.0.0.1"])

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app, client=(peer, 1234)),
            base_url="http://demo.example.com",
        ) as client:
            response = await client.get("/scheme", headers={"X-Forwarded-Proto": "https"})
            assert response.text == expected_scheme
            assert (
                await client.get("/scheme", headers={"Host": "evil.example"})
            ).status_code == 400
            assert (await client.post("/mcp", json={})).status_code == 404

    asyncio.run(exercise())
