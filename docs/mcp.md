# Public MCP experiment

One read-only tool, `list_spreadsheets(email)`, looks up an email in SQLite and returns stored
spreadsheet display names. It makes no Google calls and changes no data. Matching trims the
input and compares case-insensitively; Gmail dots/plus aliases are not rewritten. Missing names
become `Unnamed spreadsheet`, never a spreadsheet ID or URL.

This intentionally unauthenticated demo exposes account existence and spreadsheet names to
any caller with an email. Host checks and rate limits are not authentication. Only enable it
while this exposure is acceptable; OAuth and account-bound lookups are the next milestone.

Results contain `status`, `spreadsheets`, and `truncated`. Status is `ok`, `user_not_found`,
`invalid_email`, `ambiguous_user` (multiple matching accounts), or `unavailable` (database error).
An existing user with no spreadsheets returns `ok` and `[]`. Results stop at 50 names, each capped
at 255 characters, with explicit truncation. No account details, spreadsheet IDs/URLs, or content
are returned. Display names themselves are public, so avoid putting private information in them.

## Local environment, without Google credentials

From the repository root:

```bash
uv sync --extra dev
uv run python -m scripts.mcp_demo
LANGTUT_MCP_ENABLED=true LANGTUT_MCP_DATABASE_PATH=data/mcp-demo.db \
  uv run uvicorn app.mcp_server:create_mcp_app --factory \
  --host 127.0.0.1 --port 8001 --no-access-log
```

The seed command creates only `data/mcp-demo.db` (gitignored), with synthetic accounts. It refuses
to overwrite an existing file; reuse the database on later runs. It does not touch `data/app.db`.
The standalone MCP runtime does not initialize Flask, sessions, Google clients, or schema.

In another terminal:

```bash
uv run python -m scripts.mcp_smoke
uv run python -m scripts.mcp_smoke --email empty@example.com
uv run python -m scripts.mcp_smoke --email missing@example.com
uv run pytest tests/test_mcp.py
```

Expected first result: `ok`, names `Portuguese basics` and `Travel`, and `truncated: false`.
The other two calls return an empty successful list and `user_not_found`, respectively.
The smoke client performs initialization, tool discovery, and a real HTTP tool call using the
SDK. Tests use temporary databases, require no network credentials, and exercise the same protocol.

For a graphical client, run `npx -y @modelcontextprotocol/inspector` (requires Node/npm) and select
Streamable HTTP with URL `http://127.0.0.1:8001/mcp` and no authentication.

## Combined website and MCP

The existing Gunicorn entry point continues to serve only the Flask website. To test both on one
port with the usual local website configuration, use the optional ASGI entry point:

```bash
LANGTUT_MCP_ENABLED=true LANGTUT_MCP_DATABASE_PATH=data/mcp-demo.db \
  uv run uvicorn asgi:app --host 127.0.0.1 --port 8080 --no-access-log
uv run python -m scripts.mcp_smoke --url http://127.0.0.1:8080/mcp
```

Run the smoke command in a second terminal. `asgi.py` mounts Flask through `a2wsgi` and serves MCP
natively with its own lifecycle. Browser auth/session behavior stays in Flask. MCP bypasses Flask's
request-body logger. Importing the combined entry point retains `run.py`'s existing table-creation
behavior for the website; MCP's own connection is read-only.

## Configuration and eventual deployment

MCP settings use environment variables only (no `.secrets.toml` entries):

| Variable | Default / meaning |
|---|---|
| `LANGTUT_MCP_ENABLED` | `false`; disabled endpoint returns 404 |
| `LANGTUT_MCP_DATABASE_PATH` | Standalone: `data/app.db`; combined: website's configured path |
| `LANGTUT_MCP_ALLOWED_HOSTS` | JSON array; defaults to localhost/127.0.0.1 with optional ports |
| `LANGTUT_MCP_ALLOWED_ORIGINS` | JSON array; defaults to local HTTP origins |
| `LANGTUT_MCP_REQUESTS_PER_MINUTE` | `60`, shared across callers per process |

Requests are limited to 16 KiB. The simple process-wide limiter returns HTTP 429 with Retry-After;
use one worker for the experiment. It is not a distributed abuse-prevention system. Database
failures return a generic status and log no SQL parameters or submitted email. Keep debug and
request-body logging disabled in any proxy or hosting layer as well.

Before deploying, obtain explicit owner approval. The existing Docker command is unchanged:
Railway needs an explicit start-command override to use the combined runtime, for example
`uvicorn asgi:app --host 0.0.0.0 --port $PORT --workers 1 --no-access-log`.
Enable MCP and set allowed hosts to the exact deployment hostname (without scheme/path); add an
appropriate origin only if a browser client needs it. Do not use `*`. The combined runtime uses
the existing volume database by default. To retire public access, set enabled to false and restart.

ChatGPT cannot reach your laptop's loopback URL directly. Local SDK/Inspector testing proves the
server works; a ChatGPT test additionally needs reachable HTTPS (a temporary development tunnel
with synthetic data, or the approved deployment). Add the custom server in ChatGPT using `/mcp`,
choose no authentication, and ask for spreadsheets for a demo email. Verify your account supports
custom connections. Actual model tool selection still needs this manual check.

The SDK is pinned to the supported 1.x API used here; upgrades to 2.x require a deliberate migration.
