"""Exercise MCP initialization, tool discovery, and lookup over real HTTP."""

import argparse
import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def check(url: str, email: str) -> None:
    """Call the public demo using the official MCP client."""
    async with (
        streamable_http_client(url) as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        assert [tool.name for tool in tools.tools] == ["list_spreadsheets"]
        result = await session.call_tool("list_spreadsheets", {"email": email})
        if result.isError:
            raise RuntimeError("MCP tool call failed")
        print(result.structuredContent)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8001/mcp")
    parser.add_argument("--email", default="learner@example.com")
    args = parser.parse_args()
    asyncio.run(check(args.url, args.email))
