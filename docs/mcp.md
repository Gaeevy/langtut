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
LANGTUT_MCP_ENABLED=true LANGTUT_DATABASE_PATH=data/mcp-demo.db \
  uv run uvicorn app.mcp_server:create_mcp_app --factory \
  --host 127.0.0.1 --port 8001 --no-access-log
```

The seed command creates only `data/mcp-demo.db` (gitignored), with synthetic accounts. It refuses
to overwrite an existing file; reuse the database on later runs. It does not touch `data/app.db`.
The standalone MCP runtime reads the shared configuration but does not initialize Flask,
sessions, Google clients, or schema. Configured credential paths may be resolved; Google
credentials are optional for this standalone mode.

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

The standard launcher serves Flask and MCP on one port. To use your existing local database:

```bash
LANGTUT_MCP_ENABLED=true uv run python serve.py --reload
```

In another terminal:

```bash
uv run python -m scripts.mcp_smoke --url http://127.0.0.1:8080/mcp --email learner@example.com
```

Replace the synthetic email with a user already in your local database to retrieve real names;
otherwise expect `user_not_found`. Both apps use `database_path` from the local settings (normally
`data/app.db`). You can override `LANGTUT_DATABASE_PATH` to select a disposable database for both.
The combined website requires its usual Google OAuth configuration; standalone MCP does not.

`serve.py` starts Uvicorn using the resolved configuration. `asgi.create_app()` initializes the
Flask website/database, then `create_combined_app()` mounts it through `a2wsgi` alongside native
MCP. Importing `asgi` itself does not initialize the website. The old `run.py` entry point is retired.
MCP bypasses Flask's request-body logger and keeps its separate read-only database connection.
Website startup retains the existing create-missing-tables behavior; it is not a migration system.

## Configuration and eventual deployment

Configuration is resolved once per process by `app.config`: `settings.toml`, then gitignored
`.secrets.toml`, then `LANGTUT_*` environment overrides. Flask and MCP consume those same resolved
values. `MCPSettings` is only a validated value object for passing options, with no environment
loader or duplicated database defaults. Production is selected by `RAILWAY_ENVIRONMENT=production`.

| Setting / environment variable | Meaning |
|---|---|
| `database_path` / `LANGTUT_DATABASE_PATH` | Shared by Flask and MCP; local `data/app.db`, production `/app/data/app.db` |
| `mcp_enabled` / `LANGTUT_MCP_ENABLED` | Defaults false; disabled endpoint returns 404 |
| `allowed_hosts` / `LANGTUT_ALLOWED_HOSTS` | TOML/JSON array of bare hostnames, no scheme, path, or port; shared with Flask |
| `mcp_allowed_origins` / `LANGTUT_MCP_ALLOWED_ORIGINS` | Full browser origins, including scheme and optional port; MCP only |
| `mcp_requests_per_minute` / `LANGTUT_MCP_REQUESTS_PER_MINUTE` | 60 by default, shared across callers per process |
| `bind_host` / `LANGTUT_BIND_HOST` | Local `127.0.0.1`; production `0.0.0.0` |
| `port` / `LANGTUT_PORT` | Explicit setting wins, otherwise Railway `PORT`, otherwise 8080 |
| `proxy_trusted_ips` / `LANGTUT_PROXY_TRUSTED_IPS` | IP/CIDR array of trusted reverse proxies; empty by default |

Local host/origin defaults permit localhost and 127.0.0.1. Production defaults to empty lists:
the combined server refuses to start until allowed hosts are explicitly configured. MCP derives
optional-port variants of those hosts for the SDK; Flask validates the hostname itself. Neither
host nor origin checks authenticate the person making a request.

Flask does not need CORS for its current same-origin UI, and ChatGPT's server-to-server calls do
not need browser CORS. An Origin header, if present on MCP, must match the configured list; requests
without it are accepted. Configure origins only for browser clients you intentionally support.

Requests are limited to 16 KiB. The simple process-wide limiter returns HTTP 429 with Retry-After;
use one worker for the experiment. It is not a distributed abuse-prevention system. Database
failures return a generic status and log no SQL parameters or submitted email. Keep debug and
request-body logging disabled in any proxy or hosting layer as well.

Docker now launches `serve.py`, the same combined runtime used locally, with one worker.
Before deployment, configure production allowed hosts, MCP enablement, and verify the persistent
database mount. Remove any old Railway start-command override that still starts Gunicorn. Do not
copy private hostnames into tracked settings; keep them in Railway variables or local secrets.

Railway terminates HTTPS at its proxy and forwards the request internally. Uvicorn may trust
`X-Forwarded-Proto` and client-IP headers only from `proxy_trusted_ips`; the default trusts none.
Confirm the actual proxy addresses/CIDRs before configuring them, rather than trusting all peers.
This setting is consumed by `serve.py`; direct `uvicorn` commands need their own proxy options.
The existing Google OAuth production HTTPS fallback is retained. Test real Google login, secure
cookies, redirects, studying/audio, and the MCP smoke client through the combined runtime before
release; unit tests do not prove Railway's actual proxy topology. No Flask ProxyFix is layered on
top of Uvicorn's handling.

Obtain explicit owner approval immediately before production changes. To retire public MCP access,
set `mcp_enabled=false` and restart; the website continues working.

ChatGPT cannot reach your laptop's loopback URL directly. Local SDK/Inspector testing proves the
server works; a ChatGPT test additionally needs reachable HTTPS (a temporary development tunnel
with synthetic data, or the approved deployment). Add the custom server in ChatGPT using `/mcp`,
choose no authentication, and ask for spreadsheets for a demo email. Verify your account supports
custom connections. Actual model tool selection still needs this manual check.

The SDK is pinned to the supported 1.x API used here; upgrades to 2.x require a deliberate migration.
