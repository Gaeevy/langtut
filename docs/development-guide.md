# Development Guide

Practical guide for day-to-day development. Keep this short and operational.

## Local setup
```bash
git clone <repository-url>
cd langtut
uv sync
uv run pre-commit install -t pre-commit -t pre-push
```

Start server:
```bash
uv run gunicorn --bind 0.0.0.0:8080 --workers 1 --reload run:app
```

## Core commands
```bash
# tests
uv run pytest

# hooks (all files)
uv run pre-commit run --all-files

# one test module
uv run pytest tests/routes/test_learn_routes.py
```

## Project map
- `run.py` - Gunicorn entrypoint (`run:app`)
- `app/routes/` - Flask blueprints
- `app/services/` - business logic
- `app/templates/` and `app/static/` - frontend
- `app/database.py` - SQLAlchemy models
- `app/session_manager.py` - session keys/helpers
- `tests/` - pytest suite

## Development rules (high-signal only)
- Use `uv run ...` for all Python commands.
- Keep routes thin and push logic into services.
- Use `SessionManager` and `SessionKeys` (no direct `flask.session` access).
- Use SQLAlchemy ORM (no raw SQL).
- Add tests for behavior changes; prefer parametrized, DRY, MECE coverage.

## Hooks and quality gates
- `pre-commit`: lint/format/security/file checks.
- `pre-push`: mandatory `uv run pytest`.

If a hook fails, fix and re-run. Avoid `--no-verify` except true emergencies.

## Mobile testing (optional)
Use ngrok when you need real-device OAuth/audio testing:

```bash
ngrok http 8080 --url=your-name.ngrok-free.dev
```

Ensure OAuth redirect URI includes:
`https://your-name.ngrok-free.dev/oauth2callback`

## Deployment notes
- Primary target: Railway (Docker + `uv`).
- Required env vars:
  - `LANGTUT_SECRET_KEY`
  - `LANGTUT_CLIENT_SECRETS_JSON`
  - `LANGTUT_GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON`

## When adding features
1. Add/extend blueprint route.
2. Add service logic.
3. Add/update tests.
4. Update relevant docs.
