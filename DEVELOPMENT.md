# Development Guide - Language Learning Flashcard App

## Configuration Cleanup Summary

✅ **COMPLETED** - Configuration setup has been successfully consolidated and simplified!

### What Was Accomplished

1. **Unified Configuration System** (`src/config.py`)
   - Single source of truth for all application settings
   - Environment-aware configuration (local, production, testing)
   - Dual credential handling (local files vs production environment variables)
   - Automatic Railway environment detection

2. **Simplified Application Structure** (`src/__init__.py`)
   - Broke apart god-file pattern into focused functions
   - Clean application factory pattern
   - Modular initialization with proper separation of concerns

3. **Streamlined Entry Point** (`app.py`)
   - Removed development/production complexity
   - Optimized for Gunicorn deployment everywhere
   - Clear environment-specific setup

4. **Railway Configuration** (`railway.toml`)
   - Removed redundant DATABASE_PATH setting
   - Documented required environment variables
   - Simplified deployment configuration

### Environment Configuration

#### Three Environments Supported:

1. **Local Development** (`local`)
   - Debug mode enabled
   - Database: `data/app.db`
   - OAuth insecure transport enabled
   - TTS enabled

2. **Production** (`production`)
   - Debug mode disabled
   - Database: `/app/data/app.db`
   - Secure session cookies
   - Full TTS functionality

3. **Testing** (`testing`)
   - Debug mode disabled
   - Database: `:memory:`
   - TTS disabled for faster tests
   - Reduced card limits for testing

### Configuration Files

- **`settings.toml`** - Main configuration with environment sections
- **`.secrets.toml`** - Sensitive settings (not in git)
- **`railway.toml`** - Railway deployment configuration
- **`pyproject.toml`** - Poetry dependencies and linting rules

### Required Environment Variables (Production)

```bash
# Railway automatically sets:
RAILWAY_ENVIRONMENT=production

# Required to be set in Railway dashboard:
LANGTUT_CLIENT_SECRETS_JSON='{"web":{"client_id":"...","client_secret":"..."}}'
LANGTUT_GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON='{"type":"service_account","project_id":"..."}'
LANGTUT_SECRET_KEY='your-secret-key-here'
```

## Development Workflow

### Using Poetry + Gunicorn (Recommended)

```bash
# Start development server
poetry run gunicorn --bind 0.0.0.0:8080 --workers 1 --reload app:app

# Or use the convenience script
python run_dev.py
```

### Testing Application Setup

```bash
# Test application initialization (no server)
python app.py

# This will initialize the app and exit cleanly - perfect for Gunicorn
```

## Key Benefits Achieved

1. **Simplified Deployment** - No more complex development vs production logic
2. **Unified Configuration** - Single source of truth for all settings
3. **Better Development Experience** - Poetry ensures consistent dependencies
4. **Clear Environment Separation** - Automatic environment detection
5. **Maintainable Code** - Broke apart monolithic files into focused functions

## Testing

Configuration loads successfully in all environments:

```bash
# Test configuration loading
poetry run python -c "from src.config import config; print(f'Environment: {config.ENVIRONMENT}'); print(f'Debug: {config.DEBUG}'); print('✅ Configuration works!')"

# Test application startup
poetry run gunicorn --bind 0.0.0.0:8080 --workers 1 --timeout 10 app:app
```

## Next Steps

The configuration cleanup is complete! The app is now ready for:
- Consistent local development using Poetry + Gunicorn
- Simplified Railway deployment
- Easy testing with proper environment isolation
- Future feature development on a solid foundation

---

*Configuration cleanup completed successfully! 🎉*
