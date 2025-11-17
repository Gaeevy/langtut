# Architecture & Configuration

## Overview
This Flask-based language learning application follows a modular blueprint architecture with unified configuration management. The app provides ANKI-style flashcards with European Portuguese text-to-speech, Google Sheets integration, and user management.

## Core Architecture

### Application Structure
```
app.py                          # Entry point - creates Flask app
src/                           # Main application module
├── __init__.py               # Flask app factory with blueprint registration
├── routes/                   # Blueprint-based route organization
│   ├── __init__.py          # Blueprint registration
│   ├── auth.py              # OAuth authentication routes
│   ├── flashcard.py         # Core learning functionality
│   ├── settings.py          # User settings & spreadsheet config
│   ├── api.py               # TTS and API endpoints
│   ├── admin.py             # Database administration
│   └── test.py              # Testing & debugging routes
├── config.py                # Unified configuration management
├── database.py              # SQLAlchemy database models
├── session_manager.py       # Centralized session management
├── user_manager.py          # User management utilities
├── gsheet.py                # Google Sheets API integration
├── auth.py                  # OAuth authentication logic
├── tts_service.py           # Text-to-Speech service
├── models.py                # Pydantic data models
├── utils.py                 # Helper utilities
└── request_logger.py        # Request logging middleware
```

### Blueprint Organization
The application uses Flask blueprints for modular route organization:

- **Auth Blueprint** (`/auth`, `/oauth2callback`, `/clear`) - OAuth authentication
- **Flashcard Blueprint** (`/`, `/card`, `/answer`, `/feedback`) - Core learning
- **Settings Blueprint** (`/settings`, `/validate-spreadsheet`) - User configuration
- **API Blueprint** (`/api/tts`, `/api/cards`, `/api/language-settings`) - API endpoints
- **Admin Blueprint** (`/admin`, `/admin/users`) - Administrative interface
- **Test Blueprint** (`/test`) - Development and debugging

## Configuration System

### Environment Detection
The app automatically detects environments based on runtime conditions:

```python
def get_environment() -> str:
    """Environment detection using Railway's automatic variables"""

    # Testing environment
    if (os.getenv('PYTEST_CURRENT_TEST') is not None or
        os.getenv('ENVIRONMENT') == 'testing' or
        'pytest' in sys.modules):
        return 'testing'

    # Production environment - Railway sets RAILWAY_ENVIRONMENT automatically
    if os.getenv('RAILWAY_ENVIRONMENT') == 'production':
        return 'production'

    # Default to local development
    return 'local'
```

### Configuration Files
- **`settings.toml`** - Main configuration with environment sections
- **`.secrets.toml`** - Sensitive settings (excluded from git)
- **`railway.toml`** - Railway deployment configuration
- **`pyproject.toml`** - Poetry dependencies and development tools

### Environment-Specific Settings

#### Local Development
- Debug mode enabled
- Database: `data/app.db`
- OAuth insecure transport enabled
- TTS fully enabled

#### Production (Railway)
- Debug mode disabled
- Database: `/app/data/app.db`
- Secure session cookies
- Environment variables for credentials

#### Testing
- Debug mode disabled
- Database: `:memory:`
- TTS disabled for faster tests
- Reduced card limits

### Credential Management
The app uses dual credential handling:

**Local Development:**
- `client_secret.json` - OAuth credentials file
- `google-cloud-service-account.json` - TTS service account

**Production:**
- `LANGTUT_CLIENT_SECRETS_JSON` - OAuth credentials as environment variable
- `LANGTUT_GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON` - TTS service account as environment variable

## Data Architecture

### Dual-Store System
The application uses a dual-store architecture:

1. **Google Sheets** - Content management (vocabulary, cards, learning material)
2. **SQLite Database** - Application data (users, sessions, authentication state)

### Database Models
```python
class User(db.Model):
    id = Column(Integer, primary_key=True)
    google_id = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

class UserSpreadsheet(db.Model):
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    spreadsheet_id = Column(String(255), nullable=False)
    properties = Column(Text)  # JSON string for language settings
    is_active = Column(Boolean, default=False)
```

### Session Management
Centralized session management with enumerated keys:

```python
class SessionKeys(Enum):
    # Auth namespace
    AUTH_STATE = 'auth.state'
    AUTH_CREDENTIALS = 'auth.credentials'

    # User namespace
    USER_ID = 'user.id'
    USER_GOOGLE_ID = 'user.google_id'

    # Learning namespace
    LEARNING_CARDS = 'learning.cards'
    LEARNING_CURRENT_INDEX = 'learning.current_index'
```

## Key Design Decisions

### 1. Blueprint-Based Architecture
**Rationale:** Prevents monolithic code growth, enables feature-based organization, and improves maintainability.

### 2. Unified Configuration System
**Rationale:** Single source of truth for all settings, environment-aware configuration, and simplified deployment.

### 3. Dual-Store Architecture
**Rationale:** Google Sheets provides easy content management for educators, while SQLite handles application state efficiently.

### 4. Session Management Centralization
**Rationale:** Prevents session key typos, enables refactoring-safe access, and provides clear namespacing.

### 5. Pydantic Data Models
**Rationale:** Type safety, automatic validation, and clear data contracts between components.

## Development Workflow

### Local Development
```bash
# Install dependencies
poetry install

# Start development server
poetry run gunicorn --bind 0.0.0.0:8080 --workers 1 --reload app:app

# Run tests
poetry run pytest
```

### Code Quality
- Pre-commit hooks with ruff linting/formatting
- Type hints required for all functions
- Comprehensive error handling and logging
- Security scanning with bandit

### Deployment
- Railway deployment with automatic environment detection
- Poetry manages dependencies locally
- `requirements.txt` auto-generated for Railway
- Environment variables for production credentials

## Performance Considerations

### TTS Optimization
- Audio caching in Google Cloud Storage
- Base64 encoding for client-side audio playback
- Mobile-optimized audio unlock strategies

### Database Optimization
- Indexed foreign keys for user relationships
- Batch updates for card statistics
- Session-based caching for frequently accessed data

### API Rate Limiting
- Google Sheets API rate limiting handling
- TTS API caching to reduce calls
- Batch operations where possible

## Security Features

### Authentication
- Google OAuth 2.0 integration
- Secure session management
- CSRF protection via Flask-WTF

### Data Protection
- Environment-specific security settings
- Secure session cookies in production
- Input validation via Pydantic models

### API Security
- Rate limiting on API endpoints
- Input sanitization for XSS prevention
- Audit logging for sensitive operations
