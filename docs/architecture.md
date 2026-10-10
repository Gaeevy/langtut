# Architecture

LangTut is a Python Flask application with server-rendered Jinja pages and vanilla
JavaScript. Google Sheets owns vocabulary and study statistics; SQLite owns application
records. Google OAuth provides login and Sheets access; TTS/GCS provide audio.

## Runtime and boundaries

```text
Browser -> Flask blueprints ----> services -> Google Sheets / SQLite / TTS
                                     ^
ChatGPT -> native MCP adapter --------+      (SQLite names only)
```

`serve.py` launches one Uvicorn worker. `asgi.create_app()` builds Flask, initializes
SQLite and missing tables, and mounts Flask through `a2wsgi` behind the native MCP
routes. Importing `asgi.py` has no database side effects; Flask's factory alone does
not initialize the database. `run.py` is retired.

Configuration is resolved once through Dynaconf and validated by Pydantic. MCP receives
plain settings and opens a separate read-only SQLite connection. It does not use
Flask sessions, Google clients, or Flask's request-body logger. Runtime settings,
credentials, proxy handling, and healthchecks are documented in [deployment.md](deployment.md).

## Code map

| Location | Responsibility |
|---|---|
| `app/__init__.py` | Flask factory, configuration, extensions, middleware |
| `app/routes/` | HTTP parsing, HTML rendering; nested JSON blueprints in `api/` |
| `app/services/` | Business logic; study and review in `learning/` |
| `app/models.py` | Pydantic domain/request models |
| `app/database.py` | SQLAlchemy models and database initialization |
| `app/gsheet.py` | Google Sheets reads and progress writes |
| `app/session_manager.py` | Exclusive interface to Flask session state |
| `app/mcp_server.py` | MCP transport, tool declaration, limits |
| `app/services/mcp_spreadsheets.py` | Read-only email lookup |
| `app/templates/`, `app/static/` | Jinja and browser assets |

Blueprint registration lives in `app/routes/__init__.py` and `app/routes/api/__init__.py`.
Keep reusable behavior in services, not adapters. See [AGENTS.md](../AGENTS.md) for
coding and test rules.

## Persistence

| Store | Owned data |
|---|---|
| Google Sheets | Vocabulary, examples, levels, counters, last study timestamps |
| SQLite | Users, linked spreadsheets, encrypted refresh tokens, verbs, practice history |
| Filesystem session | OAuth state/access credentials, active study queues, language settings |
| GCS | Generated MP3 cache |
| Browser localStorage | Bounded TTS cache; details in [audio.md](audio.md) |

Vocabulary rows have ten columns: ID, word, translation, equivalent, example,
example translation, shown count, correct count, level, and last-shown timestamp.
Reads skip invalid rows; progress writes update G:J. Sheets owns this data until
an explicit storage migration lands. `create_all()` only creates missing tables.

## Study and audio flows

Learning reads due cards, creates tasks, and keeps the active queue in session.
Learning/review persist progress to Sheets at their save points; review early exit
also saves and retains session state if the write fails. This is not incremental
per-answer database persistence or guaranteed session recovery after interruption.

Card submission supports form POST and AJAX. AJAX renders feedback in the existing
page so audio can use the interaction that submitted the answer. Preserve the
server-rendered fallback and Jinja/JavaScript contracts. Listening fetches tab cards
and plays word/example clips in sequence. [audio.md](audio.md) owns playback,
caching, invalidation, and physical-device verification.

Irregular verbs use SQLite services and `app/import_verbs/`, independently of Sheets.
Unifying verb and vocabulary models is not an implemented feature.

## Authentication and permissions

`AuthManager` manages Google login, callbacks, refresh, and route protection. Google
subject IDs identify users; emails are not unique database identifiers. Refresh
tokens are Fernet-encrypted in SQLite; the browser session holds active credentials
and a reference to the refresh-token record.

Protected HTML routes use `require_auth`; protected JSON routes use `require_auth_api`
and return 401 on failure. They use `auth_manager.user` and `get_credentials()`.
Sessions go through `SessionManager` with namespaced `SessionKeys`. Read-only requests
do not refresh sessions by default, preventing stale background session writes.

The unused `/admin/*` routes are removed. TTS and diagnostic routes require login.
`POST /api/verbs/forms` accepts a logged-in user or the configured `X-Import-Key`;
it is not restricted to an administrator role. Language-settings validation is public
and does not access user records.

Enabled MCP deliberately permits public spreadsheet-name lookup by supplied email.
It has no user authentication, and host/origin validation does not change that.
[MCP documentation](mcp.md) owns the exact contract. The
[auth series](../path-to-auth-mcp/01-basics.md) is a proposed replacement, not existing
behavior. [AI-native](ai-native-mcp.md) and [GA](path-to-ga.md) roadmaps describe
future storage and product changes.
