# Development Guide

## Getting Started

### Prerequisites
- Python 3.11 or higher
- uv for fast dependency management ([Install uv](https://docs.astral.sh/uv/))
- Google Cloud service account (for TTS)
- Google OAuth credentials (for Sheets access)

### Quick Setup
```bash
# Clone the repository
git clone <repository-url>
cd langtut

# Install dependencies (automatically creates virtual environment)
uv sync

# Set up configuration
cp .secrets.toml.example .secrets.toml
# Edit .secrets.toml with your credentials

# Start development server
uv run gunicorn --bind 0.0.0.0:8080 --workers 1 --reload app:app
```

### Project Structure
```
langtut/
├── app.py                    # Application entry point
├── src/                      # Main source code
│   ├── __init__.py          # Flask app factory
│   ├── config.py            # Configuration management
│   ├── routes/              # Blueprint-based routes
│   │   ├── auth.py          # Authentication routes
│   │   ├── flashcard.py     # Core learning functionality
│   │   ├── api.py           # API endpoints
│   │   ├── settings.py      # User settings
│   │   ├── admin.py         # Admin interface
│   │   └── test.py          # Testing routes
│   ├── database.py          # Database models
│   ├── models.py            # Pydantic models
│   ├── tts_service.py       # TTS implementation
│   ├── gsheet.py            # Google Sheets integration
│   └── utils.py             # Helper functions
├── templates/               # Jinja2 templates
├── static/                  # Frontend assets
│   ├── js/                  # JavaScript files
│   ├── css/                 # Stylesheets
│   └── manifest.json        # PWA manifest
├── docs/                    # Documentation
├── tests/                   # Test files
├── Dockerfile               # Docker configuration for Railway
├── .dockerignore           # Docker build exclusions
├── pyproject.toml          # Project dependencies and config
└── uv.lock                 # Locked dependency versions
```

## Configuration

### Environment Detection
The application automatically detects the environment:
- **Local:** Development on local machine
- **Production:** Railway deployment (RAILWAY_ENVIRONMENT=production)
- **Testing:** Running tests (pytest detected)

### Configuration Files
- `settings.toml` - Main configuration (non-sensitive)
- `.secrets.toml` - Sensitive configuration (not in git)
- `railway.toml` - Railway deployment settings

### Environment Variables (Production)
```bash
LANGTUT_SECRET_KEY='your-secret-key-here'
LANGTUT_CLIENT_SECRETS_JSON='{"web":{"client_id":"...","client_secret":"..."}}'
LANGTUT_GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON='{"type":"service_account","project_id":"..."}'
```

## Development Workflow

### Code Quality Rules
1. **Type hints required** on all function signatures
2. **Pydantic models** for all data validation
3. **Error handling** with comprehensive try/catch blocks
4. **Logging** required for all external API calls
5. **Blueprint pattern** - no monolithic files

### Session Management
Always use SessionManager instead of direct session access:
```python
from src.session_manager import SessionManager as sm, SessionKeys as sk

# Get value
user_id = sm.get(sk.USER_ID, default_value)

# Set value
sm.set(sk.AUTH_STATE, value)

# Check existence
if sm.has(sk.AUTH_CREDENTIALS):
    # ...

# Clear namespace
sm.clear_namespace('auth')
```

### Database Operations
Use SQLAlchemy ORM, never raw SQL:
```python
from src.database import db, User, UserSpreadsheet

# Create
user = User(email='test@example.com')
db.session.add(user)
db.session.commit()

# Query
users = User.query.filter_by(email='test@example.com').all()

# Update
user.last_login = datetime.utcnow()
db.session.commit()
```

### Blueprint Structure
```python
from flask import Blueprint, request, jsonify
from typing import Dict, Any

# Create blueprint
feature_bp = Blueprint('feature', __name__, url_prefix='/feature')

@feature_bp.route('/endpoint', methods=['POST'])
def endpoint_function() -> Dict[str, Any]:
    """Clear docstring describing the endpoint."""
    try:
        # Implementation with proper error handling
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.error(f'Error in feature endpoint: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500
```

## Testing

### Running Tests
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src

# Run specific test file
uv run pytest tests/test_specific.py

# Run with debugging
uv run pytest -v -s
```

### Test Structure
```python
import pytest
from src import create_app
from src.database import db

@pytest.fixture
def app():
    """Create application for testing."""
    app = create_app()
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()

def test_endpoint(client):
    """Test API endpoint."""
    response = client.post('/api/endpoint', json={'data': 'test'})
    assert response.status_code == 200
    assert response.get_json()['success'] is True
```

### Test Routes
Available at `/test/` for development:
- `/test/test-properties` - Database properties testing
- `/test/test-tts` - TTS functionality testing
- `/test/test-gsheet` - Google Sheets integration testing

## Debugging

### Logging
The application uses structured logging:
```python
import logging
logger = logging.getLogger(__name__)

# Different log levels
logger.debug('Debug information')
logger.info('General information')
logger.warning('Warning message')
logger.error('Error occurred', exc_info=True)
```

### Debug Mode
In local development, debug mode is enabled:
- Detailed error pages
- Automatic reloading
- Enhanced logging
- OAuth insecure transport enabled

### Common Issues

#### Google Sheets API
```python
# Check authentication
if not sm.has(sk.AUTH_CREDENTIALS):
    return redirect(url_for('auth.auth'))

# Verify spreadsheet access
try:
    card_sets = read_all_card_sets(spreadsheet_id)
except Exception as e:
    logger.error(f'Sheets API error: {e}')
    # Handle error appropriately
```

#### TTS Service
```python
# Check TTS availability
if not config.TTS_ENABLED:
    return jsonify({'success': False, 'error': 'TTS disabled'})

# Handle TTS errors
try:
    audio_data = tts_service.generate_audio(text)
except Exception as e:
    logger.error(f'TTS error: {e}')
    return jsonify({'success': False, 'error': 'TTS unavailable'})
```

## Pre-commit Hooks

### Setup
```bash
# Install pre-commit hooks
uv run pre-commit install

# Run hooks manually
uv run pre-commit run --all-files
```

### Hooks Configuration
- **Ruff:** Fast Python linting and formatting
- **Bandit:** Security vulnerability scanning
- **File checks:** Trailing whitespace, JSON validation

### Bypassing Hooks (Emergency)
```bash
# Skip all hooks
git commit --no-verify

# Skip specific hook
SKIP=ruff git commit
```

## Database Management

### Database Console
```bash
# Access database directly
sqlite3 data/app.db

# Useful queries
.tables                              # List all tables
.schema user_spreadsheets           # Show table schema
SELECT * FROM users LIMIT 5;       # Query users
```

## API Development

### REST API Guidelines
- Use appropriate HTTP methods (GET, POST, PUT, DELETE)
- Return consistent JSON responses
- Include proper error handling
- Validate all inputs using Pydantic models

### API Response Format
```python
# Success response
{
    "success": true,
    "data": {...},
    "metadata": {...}
}

# Error response
{
    "success": false,
    "error": "Error message",
    "details": {...}
}
```

### Authentication
```python
from src.user_manager import is_authenticated, get_current_user

@api_bp.route('/protected', methods=['POST'])
def protected_endpoint():
    if not is_authenticated():
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    user = get_current_user()
    # ... implementation
```

## Frontend Development

### JavaScript Architecture
- **TTSManager:** Handles text-to-speech functionality
- **ListeningManager:** Manages listening mode playback
- **No framework:** Vanilla JavaScript with Bootstrap for UI

### Key JavaScript Files
- `static/js/tts.js` - TTS client implementation
- `static/js/listening.js` - Listening mode functionality
- `static/js/base.js` - Common utilities (if exists)

### Mobile Development
- PWA support with service worker
- Mobile-optimized audio unlock strategies
- Touch-friendly interface design
- Responsive CSS with Bootstrap

## Deployment

### Railway Deployment with Docker
The application uses Docker for deployment with multi-stage builds:
```bash
# Deploy to Railway (uses Dockerfile automatically)
railway up

# View logs
railway logs

# Set environment variables
railway variables set LANGTUT_SECRET_KEY=your-secret-key
```

### Local Docker Testing
```bash
# Build Docker image
docker build -t langtut:test .

# Run container locally
docker run -p 8080:8080 \
  -v $(pwd)/data:/app/data \
  -e LANGTUT_ENVIRONMENT=local \
  langtut:test
```

### Environment Variables
Required for production:
```bash
LANGTUT_SECRET_KEY
LANGTUT_CLIENT_SECRETS_JSON
LANGTUT_GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON
```

### Health Checks
The application includes health check endpoints:
- `/test` - Main application health check (used by Docker and Railway)
- `/admin` - Admin interface availability
- `/api/health` - API health status

## Performance Optimization

### Database Optimization
- Use indexed columns for frequent queries
- Implement batch operations for bulk updates
- Cache frequently accessed data in session

### TTS Optimization
- Implement audio caching with GCS
- Use client-side audio caching
- Batch audio generation requests

### Frontend Optimization
- Minimize JavaScript bundle size
- Use efficient CSS selectors
- Implement progressive loading

## Security Best Practices

### Authentication
- Use Google OAuth for user authentication
- Implement proper session management
- Validate all user inputs

### Data Protection
- Never store sensitive data in logs
- Use environment variables for secrets
- Implement proper error handling

### API Security
- Rate limiting on API endpoints
- Input validation and sanitization
- HTTPS in production

## Monitoring and Logging

### Application Logging
```python
# Request logging
logger.info(f'Request: {request.method} {request.path}')
logger.info(f'User: {user.email if user else "Anonymous"}')

# Error logging
try:
    # Operation
    pass
except Exception as e:
    logger.error(f'Operation failed: {e}', exc_info=True)
```

### Performance Monitoring
- Monitor API response times
- Track TTS cache hit rates
- Monitor Google Sheets API usage

## Common Development Tasks

### Adding a New Feature
1. Create blueprint in `src/routes/`
2. Add route handlers with proper error handling
3. Create Pydantic models for data validation
4. Add database models if needed
5. Create templates and static assets
6. Add tests
7. Update documentation

### Adding a New API Endpoint
1. Add route to appropriate blueprint
2. Implement input validation
3. Add authentication check
4. Implement business logic
5. Return consistent JSON response
6. Add error handling
7. Write tests

### Database Schema Changes
1. Update SQLAlchemy models in `src/database.py`
2. Test schema changes locally
3. Deploy to production
4. Verify schema is correct
5. Update documentation if needed

## Troubleshooting

### Common Issues
1. **Google Sheets API quota exceeded**
   - Check API usage in Google Console
   - Implement caching to reduce calls
   - Consider rate limiting

2. **TTS service unavailable**
   - Check Google Cloud service account
   - Verify TTS API is enabled
   - Check network connectivity

3. **Database locked**
   - Ensure proper connection closing
   - Check for long-running transactions
   - Restart application if needed

### Debug Commands
```bash
# Check configuration
uv run python -c "from src.config import config; print(config.DEBUG)"

# Test database connection
uv run python -c "from src.database import db; print(db.engine.execute('SELECT 1').fetchone())"

# Test TTS service
uv run python -c "from src.tts_service import tts_service; print(tts_service.generate_audio('test'))"

# Check uv environment
uv pip list  # List installed packages
uv tree      # Show dependency tree
```

## Contributing

### Pull Request Process
1. Create feature branch from main
2. Implement changes following code guidelines
3. Add tests for new functionality
4. Update documentation
5. Ensure all tests pass
6. Submit pull request

### Code Review Guidelines
- Check for proper error handling
- Verify type hints are present
- Ensure tests cover new functionality
- Review security implications
- Check performance impact

### Documentation Updates
- Update relevant documentation files
- Add code examples where appropriate
- Update API documentation
- Review for clarity and completeness
