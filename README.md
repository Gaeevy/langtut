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
uv sync --extra dev
cp .secrets.toml.example .secrets.toml
```

Fill `.secrets.toml` with local credential paths and required secrets.

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

## Documentation

Use the [documentation index](docs/README.md) for architecture, deployment, audio,
and roadmaps. Start the five-part [MCP auth guide](path-to-auth-mcp/01-basics.md) to
learn the proposed path from public lookup to per-user access.

## MCP connectivity demo

A disabled-by-default, public MCP tool lists spreadsheet display names by email.
See [MCP testing](docs/mcp.md) for synthetic/local data and the deployed smoke client.
The standard server serves both Flask and MCP; OAuth for MCP is proposed, not implemented.
