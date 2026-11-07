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
- Google Cloud CLI with user Application Default Credentials (local TTS/GCS)

### Setup
```bash
git clone <repository-url>
cd langtut
uv sync --extra dev
cp .secrets.toml.example .secrets.toml
```

Create a gitignored `credentials/` directory and save the Google OAuth client JSON as
`credentials/client_secret.json`. Fill `.secrets.toml` with the required local secrets.
Register both local callback URLs on the OAuth client:

- `http://localhost:8080/oauth2callback`
- `http://127.0.0.1:8080/oauth2callback`

For local TTS/GCS, sign in with your Google user account and select the quota project:

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID
```

The account needs access to TTS/GCS and permission to use the quota project. Leave
`google_cloud_service_account_file` and `google_cloud_service_account_json` unset locally;
also remove any service-account credential environment overrides from your terminal or IDE.
ADC is separate from the Google Sheets OAuth login. Railway continues to use its
service-account JSON through `LANGTUT_GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON`.

### Run
```bash
uv run python serve.py --reload
```

### Tests
```bash
uv run pytest
```

## Developer workflow
- Read [`AGENTS.md`](./AGENTS.md) for the project map, architectural constraints, and verification
  expectations.
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
- [`docs/deployment.md`](./docs/deployment.md)
- [`docs/audio.md`](./docs/audio.md)

## MCP connectivity demo

A disabled-by-default, read-only MCP tool can list spreadsheet display names by email.
Start with an isolated synthetic SQLite database and the local SDK smoke client; see
[`docs/mcp.md`](./docs/mcp.md) for commands, the optional combined runtime, and the explicit
public-data tradeoff. No production deployment is needed for local protocol testing.
