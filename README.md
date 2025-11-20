# Language Learning Flashcard App

A Flask web application that integrates with Google Sheets to provide ANKI-style language learning flashcards with European Portuguese text-to-speech, mobile-optimized listening mode, and comprehensive user management.

## 🚀 Features

### Core Learning Features
- **ANKI-style Flashcards:** Spaced repetition with leveling system
- **Google Sheets Integration:** Direct vocabulary management from spreadsheets
- **Statistics Tracking:** Progress monitoring with correct/incorrect counters
- **User Authentication:** Google OAuth for personalized learning

### Audio Features
- **European Portuguese TTS:** Google Cloud Text-to-Speech integration
- **Listening Mode:** Sequential audio playback with infinite loops
- **Mobile Optimization:** Chrome iOS autoplay solutions and audio unlock strategies
- **Smart Caching:** Google Cloud Storage caching for improved performance

### User Experience
- **Responsive Design:** Mobile-first interface with Bootstrap
- **Progressive Web App (PWA):** Offline capabilities and mobile installation
- **Language Settings:** Configurable original, target, and hint languages
- **Session Management:** Centralized state management with proper cleanup

## 📚 Documentation

For comprehensive information about the application, see our detailed documentation:

### 📖 [Complete Documentation](./docs/README.md)
- **[Architecture & Configuration](./docs/architecture.md)** - System design and setup
- **[Listening Mode](./docs/listening-mode.md)** - Audio playback feature
- **[User Properties System](./docs/user-properties.md)** - Language settings and configuration
- **[TTS System](./docs/tts-system.md)** - Text-to-speech implementation
- **[Development Guide](./docs/development-guide.md)** - Setup and development workflow

### Prerequisites
- Python 3.11 or higher
- uv for fast dependency management ([Install uv](https://docs.astral.sh/uv/))
- Google Cloud service account (for TTS)
- Google OAuth credentials (for Sheets access)

### Installation
```bash
# Clone the repository
git clone <repository-url>
cd langtut

# Install dependencies (uv will automatically create a virtual environment)
uv sync

# Set up configuration
cp .secrets.toml.example .secrets.toml
# Edit .secrets.toml with your credentials

# Initialize database (first time only)
uv run python init_db.py

# Start development server
# On Mac/Linux:
uv run gunicorn --bind 0.0.0.0:8080 --workers 1 --reload app:app

# On Windows (Gunicorn doesn't work - use Waitress instead):
uv run waitress-serve --host=0.0.0.0 --port=8080 app:app
# Or simply double-click: run_windows.bat
```

### Configuration
The application uses environment-aware configuration:
- **Local Development:** Uses local credential files
- **Production:** Uses environment variables on Railway
- **Testing:** Uses in-memory database and disabled TTS

## 🏗️ Architecture

### System Overview
```
Frontend (JavaScript + Bootstrap)
├── TTSManager (Audio playback)
├── ListeningManager (Sequential playback)
└── UI Components (Settings, Cards, etc.)

Backend (Flask + Blueprint Architecture)
├── Routes (auth, flashcard, api, settings, admin)
├── Services (TTS, Google Sheets, User Management)
├── Models (Pydantic + SQLAlchemy)
└── Configuration (Environment-aware)

Data Storage
├── Google Sheets (Vocabulary content)
├── SQLite (User data, sessions)
└── Google Cloud Storage (Audio cache)
```

### Key Technologies
- **Backend:** Flask with blueprint architecture
- **Database:** SQLAlchemy ORM with SQLite
- **Data Validation:** Pydantic models
- **Audio:** Google Cloud Text-to-Speech
- **Authentication:** Google OAuth 2.0
- **Deployment:** Railway with Docker + uv
- **Dependency Management:** uv (fast Python package installer)

## 📱 Mobile Support

### Audio Optimization
- **Chrome iOS:** Special "Touch Strategy" for autoplay restrictions
- **Safari iOS:** Standard unlock flow with AudioContext
- **Android:** Compatible with all major browsers
- **Caching:** Client-side and server-side audio caching

### PWA Features
- **Offline Support:** Service worker for offline functionality
- **Installation:** Add to home screen capability
- **Responsive Design:** Touch-friendly interface
- **Performance:** Optimized for mobile networks

## 🔧 Development

### Code Quality
- **Pre-commit Hooks:** Ruff linting, security scanning, formatting
- **Type Hints:** Required on all function signatures
- **Error Handling:** Comprehensive exception handling
- **Testing:** Unit and integration tests with pytest

### Development Workflow
1. **Session Management:** Centralized with enumerated keys
2. **Blueprint Pattern:** Feature-based route organization
3. **Database Operations:** SQLAlchemy ORM only
4. **API Development:** Consistent JSON responses with validation

For detailed development instructions, see [Development Guide](./docs/development-guide.md).

## 🚀 Deployment

### Railway Deployment
The application is optimized for Railway deployment with Docker:
- **Multi-stage Docker build** with uv for fast, reproducible builds
- **Automatic environment detection**
- **Environment variable configuration**
- **Gunicorn WSGI server** with production settings
- **Health check endpoints**
- **Volume mount** for SQLite database persistence at `/app/data`

### Required Environment Variables
```bash
LANGTUT_SECRET_KEY='your-secret-key-here'
LANGTUT_CLIENT_SECRETS_JSON='{"web":{"client_id":"...","client_secret":"..."}}'
LANGTUT_GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON='{"type":"service_account","project_id":"..."}'
```

### Docker Deployment
The application uses a multi-stage Dockerfile for optimized production builds:
- **Stage 1 (builder):** Install dependencies with uv
- **Stage 2 (runtime):** Minimal production image with Python 3.11.10-slim

```bash
# Build Docker image locally
docker build -t langtut:latest .

# Run container
docker run -p 8080:8080 \
  -v $(pwd)/data:/app/data \
  -e LANGTUT_SECRET_KEY='your-key' \
  langtut:latest
```

## 📊 Current Status

### ✅ Production Ready Features
- **Configuration System** - Unified environment-aware configuration
- **User Properties** - Language settings with database storage
- **Listening Mode** - Mobile-optimized sequential audio playback
- **TTS System** - Google Cloud TTS with comprehensive caching
- **Authentication** - Google OAuth integration
- **Database Management** - SQLAlchemy models with automatic migrations
- **Blueprint Architecture** - Modular route organization
- **Session Management** - Centralized session handling
- **PWA Support** - Progressive web app capabilities

### 🔧 Key Implementations
- **Chrome iOS Audio Solution:** Zero autoplay blocks achieved
- **Smart Caching:** 90% API call reduction after first loop
- **Database Migration:** Automatic schema updates
- **Error Handling:** Comprehensive error recovery
- **Performance Optimization:** Client and server-side caching

## 📝 Google Sheets Setup

The application connects to Google Sheets for vocabulary management. Required structure:

- **Column A:** id (unique identifier)
- **Column B:** word (Portuguese word)
- **Column C:** translation (English translation)
- **Column D:** equivalent (alternative translation)
- **Column E:** example (example sentence)
- **Column F:** cnt_shown (view counter)
- **Column G:** cnt_corr_answers (correct answer counter)
- **Column H:** last_shown (last shown timestamp)

### Multiple Worksheet Support
- Each worksheet tab becomes a vocabulary set
- Users can select active spreadsheet in settings
- Automatic worksheet detection and card counting

## 🛡️ Security Features

- **OAuth Authentication:** Google OAuth 2.0 integration
- **Input Validation:** Pydantic model validation
- **Session Security:** Secure session management
- **Environment Variables:** Secure credential handling
- **HTTPS:** Secure transmission in production

## 🎯 User Experience

### Learning Flow
1. **Authentication:** Google OAuth login
2. **Vocabulary Selection:** Choose from available card sets
3. **Learning Session:** Progressive difficulty with immediate feedback
4. **Audio Support:** Automatic pronunciation and listening mode
5. **Progress Tracking:** Statistics and performance monitoring

### Listening Mode
- **Sequential Playback:** Automatic word and example pronunciation
- **Infinite Loops:** Continuous playback with card reshuffling
- **Mobile Optimized:** Works on all devices including Chrome iOS
- **Cache Performance:** Instant playback after first loop

## 🔮 Future Enhancements

While the application is production-ready, potential improvements include:
- **Multiple Language Support:** Expand beyond Portuguese
- **Advanced Audio Features:** Speed control, multiple voices
- **Enhanced Analytics:** Detailed learning progress analysis
- **Offline Mode:** Enhanced PWA capabilities
- **Social Features:** Shared vocabulary sets

## 🤝 Contributing

See [Development Guide](./docs/development-guide.md) for:
- Setup instructions
- Code quality standards
- Testing procedures
- Pull request process

## 📄 License

This project is licensed under the MIT License.

---

*For detailed technical documentation, architecture details, and development guidelines, see the [docs](./docs/) directory.*
