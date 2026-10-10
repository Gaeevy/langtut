"""Real MCP protocol and read-only database boundary tests, with synthetic data."""

import asyncio
import logging
from pathlib import Path

import httpx
import pytest
from flask import Flask
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.database import User, UserSpreadsheet
from app.mcp_server import create_mcp_app
from app.mcp_settings import MCPSettings
from app.services.mcp_spreadsheets import list_spreadsheet_names, readonly_engine
from asgi import create_combined_app


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "demo.db"
    engine = create_engine(f"sqlite:///{path}")
    User.__table__.create(engine)
    UserSpreadsheet.__table__.create(engine)
    with Session(engine) as session:
        session.add_all(
            [
                User(id=1, google_user_id="one", email="learner@example.com"),
                User(id=2, google_user_id="two", email="empty@example.com"),
                User(id=3, google_user_id="three", email="other@example.com"),
                UserSpreadsheet(
                    user_id=1, spreadsheet_id="hidden-id", spreadsheet_name="Portuguese"
                ),
                UserSpreadsheet(user_id=1, spreadsheet_id="hidden-id-2", spreadsheet_name=None),
                UserSpreadsheet(user_id=3, spreadsheet_id="hidden-id-3", spreadsheet_name="Other"),
            ]
        )
        session.commit()
    engine.dispose()
    return path


def settings(database, **kwargs):
    return MCPSettings(
        enabled=kwargs.pop("enabled", True),
        database_path=database,
        allowed_hosts=["localhost", "127.0.0.1", "localhost:*", "127.0.0.1:*"],
        allowed_origins=["http://localhost", "http://localhost:*"],
        requests_per_minute=kwargs.pop("requests_per_minute", 60),
        **kwargs,
    )


@pytest.mark.parametrize(
    ("email", "status", "names"),
    [
        (" LEARNER@EXAMPLE.COM ", "ok", ["Portuguese", "Unnamed spreadsheet"]),
        ("empty@example.com", "ok", []),
        ("missing@example.com", "user_not_found", []),
        ("not-an-email", "invalid_email", []),
        ("x" * 255, "invalid_email", []),
        ("' OR 1=1 --", "invalid_email", []),
    ],
)
def test_lookup_returns_only_matching_names(database, email, status, names):
    engine = readonly_engine(database)
    try:
        result = list_spreadsheet_names(engine, email)
        assert result.model_dump() == {"status": status, "spreadsheets": names, "truncated": False}
    finally:
        engine.dispose()


def test_database_is_read_only_and_missing_file_is_not_created(database, tmp_path):
    engine = readonly_engine(database)
    with engine.connect() as connection, pytest.raises(OperationalError):
        connection.execute(text("DELETE FROM users"))
    engine.dispose()
    missing = tmp_path / "missing.db"
    with pytest.raises(ValueError):
        readonly_engine(missing)
    assert not missing.exists()


def test_ambiguous_email_does_not_merge_users(database):
    engine = create_engine(f"sqlite:///{database}")
    with Session(engine) as session:
        session.add(User(google_user_id="duplicate", email="LEARNER@example.com"))
        session.commit()
    assert list_spreadsheet_names(engine, "learner@example.com").status == "ambiguous_user"
    engine.dispose()


def test_large_result_is_explicitly_truncated(database):
    engine = create_engine(f"sqlite:///{database}")
    with Session(engine) as session:
        session.add_all(
            [
                UserSpreadsheet(user_id=1, spreadsheet_id=f"extra-{i}", spreadsheet_name="A")
                for i in range(51)
            ]
        )
        session.commit()
    result = list_spreadsheet_names(engine, "learner@example.com")
    assert len(result.spreadsheets) == 50
    assert result.truncated
    engine.dispose()


def test_disabled_mcp_needs_no_database():
    app = create_mcp_app(settings(Path("absent.db"), enabled=False))
    with TestClient(app) as client:
        assert client.post("/mcp", json={}).status_code == 404


def test_transport_rejects_bad_hosts_large_bodies_and_limits_requests(database):
    with TestClient(
        create_mcp_app(settings(database, requests_per_minute=3)), base_url="http://localhost"
    ) as client:
        headers = {
            "accept": "application/json, text/event-stream",
            "content-type": "application/json",
        }
        assert (
            client.post("/mcp", headers={**headers, "host": "evil.example"}, json={}).status_code
            == 421
        )
        assert (
            client.post(
                "/mcp", headers={**headers, "origin": "https://evil.example"}, json={}
            ).status_code
            == 403
        )
        assert client.post("/mcp", headers=headers, content="x" * 16385).status_code == 413
        assert client.post("/mcp", headers=headers, json={}).status_code == 429


def test_sdk_client_discovers_and_calls_tool_through_combined_app(database, caplog):
    web = Flask(__name__)
    web.add_url_rule("/", view_func=lambda: "website")
    app = create_combined_app(web, settings(database))

    async def exercise():
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://localhost"
            ) as http,
        ):
            assert (await http.get("/")).text == "website"
            async with (
                streamable_http_client("http://localhost/mcp", http_client=http) as (
                    read,
                    write,
                    _,
                ),
                ClientSession(read, write) as client,
            ):
                await client.initialize()
                tools = (await client.list_tools()).tools
                assert [tool.name for tool in tools] == ["list_spreadsheets"]
                assert tools[0].annotations.readOnlyHint
                assert tools[0].inputSchema["required"] == ["email"]
                for email, status in [
                    ("learner@example.com", "ok"),
                    ("absent@example.com", "user_not_found"),
                    ("bad-email", "invalid_email"),
                ]:
                    result = await client.call_tool("list_spreadsheets", {"email": email})
                    assert not result.isError
                    assert result.structuredContent["status"] == status
                    assert "hidden-id" not in str(result)
                assert (await client.call_tool("list_spreadsheets", {})).isError
                assert (await client.call_tool("nonexistent", {})).isError

    with caplog.at_level(logging.INFO):
        asyncio.run(exercise())
    assert "learner@example.com" not in caplog.text
    assert "absent@example.com" not in caplog.text


def test_database_error_does_not_expose_query_or_email(tmp_path, caplog):
    path = tmp_path / "empty.db"
    path.touch()
    app = create_mcp_app(settings(path))

    async def exercise():
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://localhost"
            ) as http,
            streamable_http_client("http://localhost/mcp", http_client=http) as (read, write, _),
            ClientSession(read, write) as client,
        ):
            await client.initialize()
            result = await client.call_tool("list_spreadsheets", {"email": "secret@example.com"})
            assert result.structuredContent["status"] == "unavailable"
            assert "secret@example.com" not in str(result)

    asyncio.run(exercise())
    assert "secret@example.com" not in caplog.text
    assert "SELECT" not in caplog.text
