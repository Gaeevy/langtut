# AGENTS.md

LangTut is a Python 3.13 Flask app for learning vocabulary from Google Sheets. It uses
server-rendered Jinja pages with vanilla JavaScript, Google OAuth, Google Cloud TTS, and SQLite
for application-owned data.

## Start here

- Read `docs/architecture.md` before changing boundaries, persistence, authentication, or session
  behavior.
- Read `docs/audio.md` before changing TTS, card submission, listening mode, or mobile playback.
- Treat `README.md` as the user-facing setup reference; keep it aligned with command changes.

## Project map

- `run.py`: Gunicorn entry point; creates the app and initializes the database.
- `app/__init__.py`: Flask app factory, configuration, Flask-Session, middleware, and blueprint
  registration.
- `app/routes/`: HTML blueprints; `app/routes/api/` contains the nested `/api` blueprints.
- `app/services/`: business logic. Learning and review logic lives in `services/learning/`.
- `app/models.py`: Pydantic domain/request models. `app/database.py`: SQLAlchemy models.
- `app/gsheet.py`: Google Sheets card reads and progress writes.
- `app/session_manager.py`: the only interface for Flask session state.
- `app/templates/`, `app/static/`: Jinja templates and vanilla JS/CSS/PWA assets.
- `config/languages.yaml`: supported TTS language/voice pairs.
- `tests/`: pytest suite, organized mostly by route/service boundary.

## Commands

Use `uv`; do not invoke the project with bare `python`, `pip`, or `pytest`.

```bash
# first-time development setup
uv sync --extra dev
uv run pre-commit install -t pre-commit -t pre-push

# local server
uv run gunicorn --bind 0.0.0.0:8080 --workers 1 --reload run:app

# verification
uv run pytest
uv run pytest tests/path/to/test_file.py
uv run ruff check .
uv run ruff format --check .
uv run pre-commit run --all-files
```

Ruff owns Python formatting (100-character lines, double quotes, import sorting). Pre-commit also
runs Bandit and file checks; pre-push runs the full test suite. Work on a feature branch because
the hooks reject commits to `main` and `master`.

## Architectural constraints

- Add routes to a feature blueprint and register new blueprints in `app/routes/__init__.py` or
  `app/routes/api/__init__.py`. Keep HTTP parsing/rendering in routes and reusable behavior in
  services.
- Google Sheets owns vocabulary, examples, levels, and card statistics. SQLite owns users, linked
  spreadsheets, encrypted refresh tokens, irregular verbs, and practice history. Use SQLAlchemy
  for application queries and `app/gsheet.py` for sheet access.
- `db.create_all()` only creates missing tables; it does not migrate changed columns. Any existing
  schema change needs an explicit migration/backfill plan.
- Use `SessionManager` with an existing `SessionKeys` member. Add a namespaced enum member before
  storing new state; never access `flask.session` directly outside the manager.
- Protect HTML routes with `@auth_manager.require_auth` and JSON routes with
  `@auth_manager.require_auth_api`. Inside protected routes, use `auth_manager.user`; use
  `auth_manager.get_credentials()` for Google API clients.
- Use Pydantic models for structured input/domain data and typed result objects for service
  boundaries. Preserve type hints on changed function signatures.
- Keep external calls observable with a module logger (`logging.getLogger(__name__)`) and avoid
  logging credentials, tokens, or full secret payloads.
- The frontend has no build step. Preserve Jinja-to-JavaScript contracts and test both the HTML
  fallback and AJAX path when changing learn/feedback flows.

## Configuration and side effects

- Dynaconf loads `settings.toml` plus gitignored `.secrets.toml`; `LANGTUT_*` environment variables
  take precedence. Runtime environments are `local` and Railway `production`.
- Never commit `.secrets.toml`, OAuth/service-account JSON, database files, session files, or new
  user-specific spreadsheet IDs/credentials.
- Importing `run.py` creates the Flask app and initializes tables. Importing `app.services.tts`
  creates the TTS singleton and may initialize Google clients. Unit tests should prefer narrower
  imports and monkeypatch external boundaries.

## Testing expectations

- Add or update tests for behavior changes. Prefer behavior-oriented names, shared fixtures, and
  parametrization for input/mode matrices.
- Mock Google Sheets, OAuth, TTS, GCS, and time/randomness where determinism matters; tests should
  not require live credentials or network access.
- Start with the narrowest relevant tests, then run `uv run pytest`. For frontend changes, include
  the existing template/static contract tests and use the manual browser checklist in
  `docs/audio.md` when audio behavior is involved.
