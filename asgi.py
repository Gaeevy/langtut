"""Optional combined runtime: native ASGI MCP plus the existing Flask website."""

from pathlib import Path

# Reuse the website's actual database unless an explicit MCP override was supplied.
from app.config import config
from app.mcp_server import MCPSettings, create_combined_app
from run import app as flask_app

settings = MCPSettings()
if "database_path" not in settings.model_fields_set:
    settings.database_path = Path(config.database_path)
app = create_combined_app(flask_app, settings)
