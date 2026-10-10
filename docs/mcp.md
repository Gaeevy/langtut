# MCP spreadsheet demo

## Tool contract

`list_spreadsheets(email)` reads stored spreadsheet display names from SQLite.
It makes no Google calls and changes no data. Email is a search filter, **not proof
of identity**: when enabled, anyone can query account existence and names by email.

Matching trims whitespace and ignores case; Gmail dot/plus aliases are not rewritten.
Multiple matching users produce `ambiguous_user`, since email is not unique in the
schema. Blank names become `Unnamed spreadsheet`. IDs, URLs, and sheet contents are
not returned.

| Result field | Meaning |
|---|---|
| `status` | `ok`, `user_not_found`, `invalid_email`, `ambiguous_user`, or `unavailable` |
| `spreadsheets` | At most 50 names, each capped at 255 characters; `ok` with `[]` means no linked sheets |
| `truncated` | More than 50 rows matched; individual name shortening has no separate flag |

The endpoint is `/mcp`, without a trailing slash. It uses the Python MCP SDK's
stateless Streamable HTTP transport with JSON responses. Requests are capped at
16 KiB and 60 per minute per process by default; excess requests return 429 with
`Retry-After`. Host checks, origin checks, and limits do not authenticate users.

## Local testing

Run commands from the repository root. For an isolated synthetic database:

```bash
uv sync --extra dev
uv run python -m scripts.mcp_demo
LANGTUT_MCP_ENABLED=true LANGTUT_DATABASE_PATH=data/mcp-demo.db \
  uv run uvicorn app.mcp_server:create_mcp_app --factory \
  --host 127.0.0.1 --port 8001 --no-access-log
```

The seed command refuses to overwrite an existing demo database. Reuse it on later
runs. Standalone MCP requires no Google credentials and does not create tables.
If credential files are configured, the shared loader may resolve their paths.

In another terminal:

```bash
uv run python -m scripts.mcp_smoke
uv run python -m scripts.mcp_smoke --email empty@example.com
uv run python -m scripts.mcp_smoke --email missing@example.com
uv run pytest tests/test_mcp.py
```

The default learner has `Portuguese basics` and `Travel`; the other calls return
an empty successful list and `user_not_found`. The client initializes MCP, discovers
the tool, calls it, and prints the structured result.

For the combined website and MCP against your local database:

```bash
LANGTUT_MCP_ENABLED=true uv run python serve.py --reload
uv run python -m scripts.mcp_smoke \
  --url http://127.0.0.1:8080/mcp --email learner@example.com
```

Run the second command in another terminal. Substitute an existing local user's
email to retrieve real names. The website requires its normal Google configuration.

## Deployed testing

Use the production URL from `operations.local.md`; do not put it in tracked files:

```bash
uv run python -m scripts.mcp_smoke \
  --url https://YOUR_DEPLOYMENT_HOSTNAME/mcp --email your-test-user@example.com
```

Connect the same HTTPS URL as a custom MCP server in ChatGPT with no authentication
for this experiment. Ask it to list spreadsheets for the test email and inspect the
actual tool call and result. Protocol success alone does not prove correct model
selection. Refer to the [OpenAI connection guide](https://developers.openai.com/plugins/deploy/connect-chatgpt)
for the current account-specific setup flow.

A 404 can mean MCP is disabled or the URL has a trailing slash. A 403 with
`Invalid Origin header` means the client sent an origin outside the configured
list. A 421 means the MCP host check failed. Check the response before changing
configuration; allow exact intended origins rather than disabling validation.

[Deployment](deployment.md) owns configuration, enable/disable commands, and proxy
behavior. [Architecture](architecture.md) owns runtime boundaries. The
[five-part auth guide](../path-to-auth-mcp/01-basics.md) describes the proposed
replacement for public email lookup; OAuth is not implemented by this demo.
