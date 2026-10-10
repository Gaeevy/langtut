"""Compose the native MCP application and Flask website under one ASGI server."""

import os

from a2wsgi import WSGIMiddleware
from flask import Flask
from starlette.applications import Starlette

from app.mcp_server import create_mcp_app
from app.mcp_settings import MCPSettings


def create_combined_app(flask_app: Flask, settings: MCPSettings) -> Starlette:
    """Serve MCP natively and dispatch remaining paths to the existing Flask website."""
    app = create_mcp_app(settings)
    app.mount("/", WSGIMiddleware(flask_app))
    return app


def create_app() -> Starlette:
    """Initialize the website/database once and compose both applications."""
    from app import create_app as create_flask_app
    from app.config import Environment, config
    from app.database import ensure_tables, init_database

    if not config.allowed_hosts:
        raise ValueError("Configure LANGTUT_ALLOWED_HOSTS before starting the service")
    if not config.client_secrets_file_path:
        raise ValueError("Google OAuth credentials are required for the combined website")

    if config.environment == Environment.LOCAL:
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    web = create_flask_app()
    init_database(web)
    with web.app_context():
        ensure_tables()
    return create_combined_app(web, config.mcp_settings())
