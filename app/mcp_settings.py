"""Validated MCP options supplied by the shared application configuration or tests."""

from pathlib import Path

from pydantic import BaseModel, Field


class MCPSettings(BaseModel):
    """Plain values, not a second environment/configuration loader."""

    enabled: bool
    database_path: Path
    allowed_hosts: list[str]
    allowed_origins: list[str]
    requests_per_minute: int = Field(ge=1, le=10000)
