# Architecture

This describes the code in the current checkout. Use the [deployment guide](deployment.md)
to verify a release and the [documentation index](README.md) for each topic's primary reference.

## Runtime and code map

```text
Browser -> Flask routes -> application services -> Google Sheets / SQLite / TTS
ChatGPT -> native MCP adapter -> read-only SQLite spreadsheet-name lookup
```

`serve.py` starts one Uvicorn worker. `asgi.create_app()` builds Flask, checks the auth
schema, initializes missing tables, and mounts Flask behind the native MCP routes.
Importing `asgi` has no database side effects. The Flask factory configures extensions
and Google OAuth, while database initialization belongs to the combined factory.

| Location | Responsibility |
|---|---|
| `app/__init__.py`, `app/config.py` | Flask setup and shared Dynaconf/Pydantic configuration |
| `app/routes/`, `app/routes/api/` | HTML and JSON request adapters, blueprint registration |
| `app/services/` | Application behavior, with learn/review under `learning/` |
| `app/services/auth_manager.py` | Browser login, guards, and account-action orchestration |
| `app/services/google_oauth.py`, `app/services/users.py` | Google authorization and verified-identity account lookup |
| `app/services/google_credentials.py` | Sheets grants, refresh, rotation, and access-token cache |
| `app/models.py`, `app/database.py` | Pydantic input/domain models and SQLAlchemy persistence |
| `app/gsheet.py` | Sheets reads and progress writes |
| `app/session_manager.py` | Flask session state and namespaced keys |
| `app/mcp_server.py`, `app/services/mcp_spreadsheets.py` | MCP transport and stored-name lookups |
| `app/templates/`, `app/static/` | Jinja, JavaScript, CSS, and PWA assets |
| `config/languages.yaml` | TTS language and voice pairs |
| `scripts/migrate_auth.py`, `tests/` | Auth migration and automated verification |

[AGENTS.md](../AGENTS.md) owns implementation rules and required checks.

## Data ownership and study state

| Store | Data |
|---|---|
| Google Sheets | Vocabulary, examples, levels, counters, and last-shown timestamps |
| SQLite | Users, linked spreadsheets, encrypted Sheets grants, verbs, and practice history |
| Filesystem session | LangTut login and OAuth transactions, study queues, answers, and language selection |
| GCS | Generated MP3 cache |
| Browser localStorage | Bounded TTS cache described in [audio.md](audio.md#caching) |

A vocabulary row has ten columns, in order: ID, word, translation, equivalent,
example, example translation, shown count, correct count, level, and last-shown
timestamp. Reads skip invalid rows. Progress writes update G:J for requested cards.

Learn and review keep active state in the browser's server-side session. Learn saves
progress at completion or early exit. Review saves its stack after the final card or
saves reviewed cards on early exit. Failed writes retain state for retry. Accepted
answers become durable at these save points. Irregular verbs use SQLite independently.

Both form submission and AJAX are supported. AJAX renders feedback in the current
page so playback can use the submit gesture. [Audio](audio.md) owns browser playback,
cache behavior, and the physical-device checklist.

## Identity, sessions, and Sheets access

```text
Google identity -> local User -> LangTut browser session
Signed-in user -> Sheets consent for the same Google identity -> GoogleSheetsConnection
Trusted User.id -> GoogleCredentialsService -> Google access token -> Sheets operation
```

`User.google_user_id` is the stable Google subject. Email and name are profile fields.
OAuth client configuration loads at Flask application setup. Sign-in requests identity
scopes. Connect/Reconnect requests identity and Sheets scopes with offline access.
Both callbacks verify the ID token. The connection callback also checks the initiating
local user, session version, and matching Google subject.

The session holds up to eight pending transactions keyed by OAuth state. Each records
its purpose, redirect URI, PKCE verifier, and ten-minute expiry. A callback consumes its
own transaction. Login rotates the session ID and creates a seven-day, fixed-expiry login.
Guards check the local user, Google subject, expiry, and session version.

| Action | LangTut login | Sheets connection |
|---|---|---|
| Log out | End this browser session | Retain |
| Log out everywhere | Increment the user session version and end this login | Retain |
| Disconnect Google Sheets | Retain | Delete the local grant and cached access |
| Google rejects the stored grant as invalid | Retain | Delete the unusable connection and require reconnect |

One `GoogleSheetsConnection` per local user stores the encrypted refresh token,
Google subject, known granted scopes, and timestamps. Access tokens stay in a cache
of at most 128 entries per process. Refreshes for a user are serialized within that
process. Callers receive fresh Google `Credentials` objects containing access tokens.
The service runs in an application context without a Flask request or session.
Multiple workers need a review of cross-process refresh coordination.

Sheets operations take explicit trusted user and spreadsheet IDs. Routes resolve
the user's active spreadsheet. Settings validation checks Google access before linking
new spreadsheets. A Google 401 triggers one forced refresh and retry. A temporary
proactive refresh failure can retain a still-valid token. Forced refresh evicts the
rejected token first. Google file-permission 403 responses retain the connection.

## HTTP and MCP boundaries

HTML guards redirect anonymous users to sign-in. JSON guards return 401. A missing
Sheets connection produces a connection page or JSON 403 with
`google_sheets_connection_required`. Credential-service outages produce 503 with
`google_sheets_unavailable` for JSON callers. Connect, logout, and disconnect use
CSRF-protected POSTs. Other routes retain their existing protection and validation.

TTS and diagnostics require login. `POST /api/verbs/forms` accepts either a valid
LangTut login or `X-Import-Key`. Language-settings validation is public.

The public MCP contract and private-MCP remaining work live in [mcp.md](mcp.md).
`list_spreadsheet_names_for_user(engine, user_id)` is an internal service boundary for
trusted application code. Its caller establishes identity. Complete learn/review
workflows still depend on `SessionManager` and need a state adapter for future MCP use.

Existing auth schemas require the explicit [auth cutover](deployment.md#auth-cutover).
Legacy refresh-token rows remain available for reviewed rollback and later cleanup.
