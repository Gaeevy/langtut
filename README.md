# LangTut

Python 3.13 Flask app for vocabulary practice with Google Sheets, irregular verbs,
and Google Cloud text-to-speech. The browser interface uses Jinja and vanilla JavaScript.

Sign in with Google to practice irregular verbs. Choose **Connect Google Sheets** to
use vocabulary spreadsheets from the same Google account. You can study and review
cards by worksheet, or listen to their words and examples.

## Local setup

Install Python 3.13 and `uv`, and create a Google OAuth web client.
Run from the repository root.

```bash
uv sync --extra dev
cp .secrets.toml.example .secrets.toml
uv run pre-commit install -t pre-commit -t pre-push
```

Save the OAuth client JSON as `credentials/client_secret.json`, then fill the
Fernet encryption key in `.secrets.toml`. Set a stable Flask `SECRET_KEY` there to
preserve session signing across restarts. The example file includes key-generation
commands. Keep these files outside version control.

Register both redirect URIs on the Google OAuth client.

- `http://localhost:8080/oauth2callback`
- `http://127.0.0.1:8080/oauth2callback`

For local TTS and audio caching, install the Google Cloud CLI and configure user
Application Default Credentials (ADC).

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID
```

The account needs TTS/GCS access and permission to use the quota project. Leave
`google_cloud_service_account_file` and `google_cloud_service_account_json` unset,
including environment overrides, to use ADC. Google OAuth and ADC authorize separate
parts of the app. To run without audio, set `LANGTUT_TTS_ENABLED=false`.

Before upgrading an existing database, follow the [auth cutover](docs/deployment.md#auth-cutover).
For a new installation, the combined launcher creates the SQLite tables.

```bash
uv run python serve.py --reload
```

Open `http://localhost:8080`. Local defaults use `data/app.db` and `flask_session/`.

## Development and operations

[AGENTS.md](AGENTS.md) owns coding rules and verification commands.
[Architecture](docs/architecture.md) explains persistence, login sessions, and Sheets
connections. [Deployment](docs/deployment.md) owns Railway settings and migration
procedures. The [MCP guide](docs/mcp.md) covers the public spreadsheet-name demo.

Use the [documentation index](docs/README.md) to find audio details and future plans.
