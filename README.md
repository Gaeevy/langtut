# Language Learning Flashcard App

Flask app for learning European Portuguese with Google Sheets-backed card content and Google Cloud TTS.

## What it does
- Study and review vocabulary by worksheet/tab.
- Run listening mode with cached audio playback.
- Keep user/app state in SQLite while card content lives in Google Sheets.
- Authenticate users with Google OAuth.

## Quick start
### Prerequisites
- Python 3.13
- `uv`
- Google OAuth client credentials
- Google Cloud service account (TTS)

### Setup
```bash
git clone <repository-url>
cd langtut
uv sync
cp .secrets.toml.example .secrets.toml
```

Fill `.secrets.toml` with local credential paths and required secrets.

### Run
```bash
uv run gunicorn --bind 0.0.0.0:8080 --workers 1 --reload run:app
```

### Tests
```bash
uv run pytest
```

## Developer workflow
- Install hooks once per clone:
  ```bash
  uv run pre-commit install -t pre-commit -t pre-push
  ```
- Pre-commit handles lint/format/security basics.
- Pre-push runs the test suite.

## Architecture at a glance
- Backend: Flask blueprints + service layer.
- Stores:
  - Google Sheets for vocabulary/card content.
  - SQLite (SQLAlchemy) for user/app state.
- Frontend: Jinja templates + vanilla JS/CSS.

See [`docs/architecture.md`](./docs/architecture.md) for details.

## Documentation
- [`docs/README.md`](./docs/README.md) (index)
- [`docs/architecture.md`](./docs/architecture.md)
- [`docs/audio.md`](./docs/audio.md)
- [`docs/development-guide.md`](./docs/development-guide.md)
