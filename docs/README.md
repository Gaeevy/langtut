# Documentation Index

## Docs

### [Architecture & Configuration](./architecture.md)
System design: Flask blueprints, configuration, dual-store (Google Sheets + SQLite), session management, deployment.

### [Audio System](./audio.md)
TTS, audio playback, mobile autoplay, caching, and listening mode -- all in one place.

### [Development Guide](./development-guide.md)
Setup, code quality rules, testing, debugging, mobile testing with ngrok, deployment.

## Quick Reference

### Running Locally
```bash
uv run gunicorn --bind 0.0.0.0:8080 --workers 1 --reload run:app
```

### Mobile Testing
```bash
ngrok http 8080 --url=evette-nontransposing-barabara.ngrok-free.dev
```
See [Development Guide](./development-guide.md#mobile-testing-with-ngrok) for full setup.

### Architecture

```
Frontend (Vanilla JS + Bootstrap)
├── TTSManager       → audio fetch, cache, playback, mobile unlock
├── card.js          → AJAX answer submission + in-page feedback
├── ListeningManager → sequential card playback
└── modes.js         → pick_one / build_sentence / build_word UI

Backend (Flask + Blueprints)
├── Routes: auth, learn, review, index, settings, admin, api/tts
├── Services: TTS, Google Sheets, auth, learning
├── Models: Pydantic + SQLAlchemy
└── Config: Dynaconf (settings.toml / .secrets.toml)

External Services
├── Google Cloud TTS  → audio generation
├── Google Sheets API → vocabulary content
├── Google OAuth      → authentication
└── Google Cloud Storage → audio cache
```
