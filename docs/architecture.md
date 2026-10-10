# Architecture & Configuration

## System overview

LangTut is a server-rendered Flask application with a small vanilla-JavaScript frontend. Users
authenticate with Google, choose a Google Sheets workbook as their vocabulary source, and study or
review cards. SQLite stores application-owned state; Google Cloud TTS and Cloud Storage provide and
cache audio.

```text
Browser (Jinja + vanilla JS)
        |
        v
Flask blueprints -> services -> Pydantic domain models
        |                |
        |                +-> Google Sheets (cards and learning progress)
        +-> SQLAlchemy/SQLite (users, auth tokens, sheet links, verbs)
        +-> filesystem sessions
        +-> Google TTS -> GCS audio cache
```

## Runtime composition

`serve.py` launches Uvicorn using the single resolved `app.config` object. The ASGI factory
`asgi.create_app()` creates Flask, initializes its database and missing tables, and composes the
native MCP endpoint with Flask through `a2wsgi`. Importing `asgi.py` has no database side effects.
The old Gunicorn `run.py` entry point is retired; Docker and local development use the same launcher.

Flask's own factory still does not initialize the database. `create_all()` creates missing tables,
but does not migrate changed columns. Configuration is resolved once per process through Dynaconf,
validated by a plain Pydantic model, and shared by both apps. MCP uses the same database path with
a separate read-only connection. Tests can inject MCP options directly without loading credentials.

## Code organization

```text
serve.py                      Uvicorn launcher
asgi.py                       combined application factory
app/
├── __init__.py                 app factory
├── config.py                   Dynaconf -> typed Config object
├── database.py                 SQLAlchemy models and initialization
├── gsheet.py                   card reads and progress writes
├── models.py                   Pydantic domain/request models
├── session_manager.py          namespaced session access
├── routes/
│   ├── auth.py                 Google OAuth entry/callback/logout
│   ├── index.py                login, setup, and dashboard
│   ├── learn.py                study flow and AJAX/form answer paths
│   ├── review.py               browse/flip review flow
│   ├── settings.py             linked spreadsheet management
│   ├── verbs.py                irregular-verb pages
│   ├── test.py                 authenticated diagnostic endpoints
│   └── api/                    cards, TTS, languages, verbs
├── services/
│   ├── auth_manager.py         OAuth, refresh, and route protection
│   ├── learning/               sessions, queues, modes, statistics
│   ├── listening_cards_service.py
│   ├── settings_service.py
│   ├── tts.py
│   └── verbs_service.py
├── templates/                  server-rendered UI
└── static/                     vanilla JS/CSS and PWA files
```

Blueprints are registered in `app/routes/__init__.py`. API sub-blueprints are nested below the
`/api` prefix in `app/routes/api/__init__.py`.

## Request and domain flows

### Learn and review

`LearnService` reads due cards from the active workbook, creates a level-dependent task pipeline,
and stores the serialized queue/state in the `learning.*` session namespace. Answer processing
updates per-card statistics and writes completed session progress back to the sheet in a batch.

`ReviewService` loads all cards for a tab and uses the separate `review.*` namespace for a
one-pass stack. A forgotten card loses one level; a remembered card keeps its level. Both choices
update the card's last-shown timestamp in the review session. The full stack is written to Google
Sheets once, after the final card is reviewed. Ending early writes only cards already reviewed and
keeps the active session intact if that batch write fails.
`CardSessionManager` provides the common serialized-card session behavior.

The learn answer route supports both normal form POST/redirect and JSON/AJAX. The AJAX path renders
feedback in place so mobile audio remains in the same page and gesture context. Keep both paths
working.

### Listening and TTS

`GET /api/cards/<tab_name>` uses `ListeningCardsService` to load and shuffle cards that have both a
word and example. `POST /api/tts/speak` selects a voice from the session's target language, checks
the GCS cache when workbook and sheet identifiers are provided, and returns base64 MP3. See
[`audio.md`](./audio.md) for the browser-side playback details.

### Irregular verbs

Verb forms and per-user practice history are application-owned, so this feature uses SQLite rather
than Google Sheets. HTML routes live in `routes/verbs.py`; JSON/import endpoints live in
`routes/api/verbs.py`; persistence and selection behavior is in `VerbsService` and
`app/import_verbs/`.

## Persistence boundaries

| Store | Owned data | Main access point |
|---|---|---|
| Google Sheets | card text, examples, counters, levels, last-shown time | `app/gsheet.py` |
| SQLite | users, linked workbooks and language settings, encrypted refresh tokens, verb data | `app/database.py` + services |
| Filesystem session | OAuth access token/state and refresh-token row ID, active learn/review queues, target language | `SessionManager` |
| Google Cloud Storage | generated MP3 cache | `TTSService` |
| Browser localStorage | base64 TTS cache keyed by trimmed text | `TTSManager` |

The SQLite models are `User`, `RefreshToken`, `UserSpreadsheet`, `VerbInfinitive`, `VerbTense`,
`VerbForm`, and `UserVerbInteraction`. `UserSpreadsheet.properties` stores validated language
settings as JSON.

Each vocabulary worksheet has a header row followed by ten positional columns: ID, word,
translation, equivalent, example, example translation, shown count, correct count, level, and last
shown. Reads skip invalid rows; progress writes update only the final four statistics columns (G:J).

## Authentication and session state

`AuthManager` owns OAuth flow creation, callbacks, credential refresh, and logout:

1. the login route stores OAuth state and redirect URI in the session;
2. the callback identifies or creates the SQLite user;
3. the short-lived access token and expiry live in the filesystem-backed session;
4. the refresh token is Fernet-encrypted in SQLite and referenced by its row ID from the session;
5. protected requests refresh credentials transparently when needed.

Server-side sessions are written only when modified by default
(`session_refresh_each_request = false`). This prevents slower, read-only background requests such
as TTS prefetches from overwriting newer authentication or learning state with an older snapshot.

HTML routes use `@auth_manager.require_auth` (redirect on failure). JSON endpoints use
`@auth_manager.require_auth_api` (JSON `401`). Session state goes through `SessionManager` and the
namespaced `SessionKeys` enum; current namespaces are `auth`, `user`, `learning`, `review`, `tts`,
and `test`.

The unused `/admin/*` endpoints have been retired, including exports and custom SQL queries.
TTS status/generation and diagnostic routes require authentication. Verb imports at
`POST /api/verbs/forms` currently accept any authenticated user or a configured `X-Import-Key`;
this is not an administrator-only permission. Language-settings validation remains public and
does not read or write user records.

## Configuration and deployment

Dynaconf reads `settings.toml`, then gitignored `.secrets.toml`, with `LANGTUT_*` environment values
taking precedence. There are two runtime environments:

- `local` by default: `data/app.db`, `flask_session/`, insecure OAuth transport enabled by `asgi.create_app()`;
- `production` when `RAILWAY_ENVIRONMENT=production`: `/app/data/app.db`,
  `/app/data/flask_session`, secure session cookies.

Local credential files are configured in `.secrets.toml`. Railway supplies OAuth and service-account
JSON through `LANGTUT_CLIENT_SECRETS_JSON` and
`LANGTUT_GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON`. `LANGTUT_ENCRYPTION_KEY` is required to decrypt stored
refresh tokens; `LANGTUT_SECRET_KEY` should be stable so sessions remain valid across restarts.

Railway builds the `Dockerfile`, runs `serve.py`, and expects a persistent volume mounted at
`/app/data`. Language-to-voice mappings are configured separately in `config/languages.yaml`.

## Optional MCP adapter

`app/mcp_server.py` exposes the intentionally public `list_spreadsheets(email)` experiment over
Streamable HTTP when explicitly enabled. `app/services/mcp_spreadsheets.py` uses the existing
SQLAlchemy models through a separate SQLite read-only engine and returns names only. No schema
migration, Google calls, or browser session identity is involved. This is a deliberate temporary
exception to authenticated application routes: caller-supplied email is only a search filter.

`asgi.py` combines the native ASGI MCP application with Flask through `a2wsgi`. The shared
`allowed_hosts` setting protects both entry points. The same-origin website does not enable CORS;
MCP has independent Origin-header validation. `serve.py` trusts forwarded headers only from the
explicit `proxy_trusted_ips` list. Production hostnames/proxy ranges must be configured before
release. See [MCP setup](mcp.md) for local tests and deployment configuration.
