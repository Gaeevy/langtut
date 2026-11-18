# MCP

## Tool contract

The enabled public demo exposes `list_spreadsheets(email)`. Anyone can query stored
account existence and spreadsheet display names using an email search filter. Results
come from SQLite. The tool reads data without Google calls or database writes.

Matching trims whitespace and ignores case. Gmail dot/plus aliases retain their literal
form. Multiple users matching an email return `ambiguous_user`. Blank display names
become `Unnamed spreadsheet`. Responses contain names and status only.

| Field | Meaning |
|---|---|
| `status` | `ok`, `user_not_found`, `invalid_email`, `ambiguous_user`, or `unavailable` |
| `spreadsheets` | Up to 50 names, each at most 255 characters; `ok` with `[]` means an empty library |
| `truncated` | More than 50 rows matched; individual-name shortening has no separate flag |

The endpoint is `/mcp`, using stateless Streamable HTTP and JSON responses through
the Python MCP SDK. Requests are capped at 16 KiB. The default per-process limit is
60 per minute; excess requests return 429 with `Retry-After`.

Host validation checks the requested destination. An `Origin` header, when present,
must match the configured MCP origins. An empty origin list accepts requests with no
Origin header and rejects requests that include one. These checks operate alongside
the public tool's access policy. [Deployment configuration](deployment.md#runtime-and-configuration)
owns enablement and runtime variables.

## Local testing

From the repository root, create a disposable database and run standalone MCP.

```bash
uv run python -m scripts.mcp_demo
LANGTUT_MCP_ENABLED=true LANGTUT_DATABASE_PATH=data/mcp-demo.db \
  uv run uvicorn app.mcp_server:create_mcp_app --factory \
  --host 127.0.0.1 --port 8001 --no-access-log
```

The seed command refuses to overwrite the demo database; reuse it on later runs.
Standalone MCP opens an existing database read-only and requires no Google credentials.
Shared configuration may resolve configured credential paths. For dependency setup,
use the [README](../README.md#local-setup).

In another terminal, run the smoke client and protocol tests.

```bash
uv run python -m scripts.mcp_smoke
uv run python -m scripts.mcp_smoke --email empty@example.com
uv run python -m scripts.mcp_smoke --email missing@example.com
uv run pytest tests/test_mcp.py
```

The default learner returns `Portuguese basics` and `Travel`. The other calls return
an empty library and `user_not_found`. The client initializes MCP, discovers the tool,
and prints its structured result.

For combined local website/MCP testing, set `LANGTUT_MCP_ENABLED=true` on the
[standard launcher](../README.md#local-setup), then call the smoke client with
`--url http://127.0.0.1:8080/mcp`. The combined app needs its normal OAuth configuration.
Use a synthetic database or a test user's email for the lookup.

## Deployed testing and troubleshooting

Take the target from gitignored `operations.local.md`.

```bash
uv run python -m scripts.mcp_smoke \
  --url https://YOUR_DEPLOYMENT_HOSTNAME/mcp --email your-test-user@example.com
```

For ChatGPT, follow the current account's custom MCP connection workflow using the
same HTTPS URL and the demo's unauthenticated access setting. Verify the actual tool
call and result from a prompt. [OpenAI connection guide](https://developers.openai.com/plugins/deploy/connect-chatgpt)

| Response | Check |
|---|---|
| 404 | MCP enablement and the exact `/mcp` path; `/mcp/` is reserved with a 404 response |
| 403 with `Invalid Origin header` | The client's Origin against configured allowed origins |
| 421 | The requested hostname against allowed hosts |
| 429 | The per-process request budget and `Retry-After` |

Protocol tests prove discovery and calls. Test real client prompts separately to verify
tool selection and inputs. Record the ChatGPT surfaces and account access actually tested.

## Private MCP remaining work

The checkout provides internal `list_spreadsheet_names_for_user(engine, user_id)` and
request-independent Google credential refresh. A future authenticated adapter must
establish a trusted local user before using those services.

Implement these requirements together before exposing `list_my_spreadsheets()`.

- MCP OAuth authorization/resource discovery with Auth0 token validation.
- A verified issuer/subject mapping to local `User.id`.
- Audience, expiry, and per-tool scope enforcement.
- Client sign-in, expiry/reconnection, and Sheets connection UX.
- Deployment checks for authenticated calls, rejected tokens, and user isolation.

The public tool continues to accept email. Internal user-ID lookup remains available
to trusted application code. Complete learn/review workflows additionally need a state
adapter for their browser sessions. [Architecture](architecture.md#http-and-mcp-boundaries)
owns those boundaries. [AI-native MVP](ai-native-mcp.md) owns future vocabulary tools
and write reliability. Recheck client and protocol requirements when implementing.
[MCP authorization specification](https://modelcontextprotocol.io/specification/latest/basic/authorization)
