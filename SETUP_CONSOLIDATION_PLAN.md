# Language Learning Flashcard App - Setup Consolidation Plan

## Overview

This document outlines the plan to consolidate the fragmented application setup process into a unified, maintainable system. The goal is to reduce complexity, eliminate duplication, and create a single source of truth for all configuration and initialization.

## Current State Analysis

### Current Configuration & Environment Variables (Categorized)

#### **1. Application Core Settings**
- `SECRET_KEY` - Flask session encryption key
- `DEBUG` - Flask debug mode (dev: true, prod: false)
- `MAX_CARDS_PER_SESSION` - Learning session limit (default: 10)
- `SPREADSHEET_ID` - Default Google Sheets ID

#### **2. Google OAuth Configuration**
- `CLIENT_SECRETS_FILE` - Local OAuth credentials file path
- `CLIENT_SECRETS_JSON` - Production OAuth credentials (env var)
- `SCOPES` - OAuth permission scopes array
- `API_SERVICE_NAME` - Google API service name ("sheets")
- `API_VERSION` - Google API version ("v4")

#### **3. Google Cloud TTS Configuration**
- `TTS_ENABLED` - Enable/disable TTS functionality
- `TTS_LANGUAGE_CODE` - TTS language ("pt-PT")
- `TTS_VOICE_NAME` - TTS voice selection ("pt-PT-Standard-A")
- `TTS_AUDIO_ENCODING` - Audio format ("MP3")
- `GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE` - Local service account file
- `GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON` - Production service account (env var)
- `GCS_AUDIO_BUCKET` - Audio caching bucket ("langtut-tts")

#### **4. Flask Session Configuration**
- `SESSION_TYPE` - Session storage type ("filesystem")
- `SESSION_PERMANENT` - Session permanence (false)
- `SESSION_USE_SIGNER` - Session signing (true)
- `SESSION_COOKIE_SECURE` - HTTPS-only cookies (dev: false, prod: true)
- `SESSION_COOKIE_HTTPONLY` - HTTP-only cookies (true)
- `SESSION_COOKIE_SAMESITE` - SameSite policy ("Lax")

#### **5. Flask JSON Configuration**
- `JSON_AS_ASCII` - ASCII-only JSON (false)
- `JSONIFY_MIMETYPE` - JSON response MIME type

#### **6. Environment Detection Variables**
- `FLASK_ENV` - Flask environment ("development"/"production")
- `ENVIRONMENT` - General environment indicator
- `PORT` - Server port (Railway/Heroku sets this)
- `RAILWAY_ENVIRONMENT` - Railway platform indicator
- `RAILWAY_SERVICE_NAME` - Railway service identifier
- `OAUTHLIB_INSECURE_TRANSPORT` - OAuth dev mode (set to "1" in dev)

#### **7. Database Configuration**
- `DATABASE_PATH` - Database file path (Railway: "/app/data/app.db")
- `SQLALCHEMY_DATABASE_URI` - Auto-generated from DATABASE_PATH
- `SQLALCHEMY_TRACK_MODIFICATIONS` - SQLAlchemy change tracking (false)

#### **8. Configuration Files**
- `settings.toml` - Main configuration file
- `.secrets.toml` - Secret configuration (not in git)
- `railway.toml` - Railway deployment configuration
- `Procfile` - Gunicorn deployment configuration

### Current Problems

#### **1. Fragmented Configuration**
- Settings scattered across 4+ files
- 25+ individual imports in `__init__.py`
- Duplicated environment detection logic
- Complex production vs development handling

#### **2. Complex Credential Management**
- Runtime temporary file creation for production secrets
- Multiple credential sources (files vs env vars)
- Validation scattered across multiple files

#### **3. Split Initialization Process**
- `app.py` - Entry point and environment detection
- `src/config.py` - Configuration loading and credential management
- `src/__init__.py` - Flask app creation and service setup
- `src/database.py` - Database initialization
- Various services initialized in multiple places

#### **4. Deployment Configuration Split**
- Railway-specific settings in `railway.toml`
- Application settings in `settings.toml`
- Production overrides in environment variables
- Gunicorn configuration in `Procfile`

## Simple Consolidation Strategy

### **Goal: Minimal Changes, Maximum Impact**

Instead of over-engineering, let's solve the actual problems with minimal risk and complexity.

### **Phase 1: Define Three Clear Environments**

#### **Environment Names**
- **`local`** - Development on local machine
- **`production`** - Railway deployment
- **`testing`** - Running tests (pytest)

#### **Environment Detection Logic** (in `src/config.py`)
```python
def get_environment() -> str:
    """Simple, clear environment detection using Railway's automatic variables"""

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

### **Phase 2: Consolidate All Configuration**

#### **Enhanced `settings.toml`**
```toml
[default]
# Shared settings across all environments
max_cards_per_session = 10
spreadsheet_id = "15_PsHfMb440wtUgZ0d1aJmu5YIXoo9JKytlJINxOV8Q"

# Google OAuth
client_secrets_file = "client_secret.json"
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile", "openid"]
api_service_name = "sheets"
api_version = "v4"

# Google TTS
tts_enabled = true
tts_language_code = "pt-PT"
tts_voice_name = "pt-PT-Standard-A"
tts_audio_encoding = "MP3"
google_cloud_service_account_file = "google-cloud-service-account.json"
gcs_audio_bucket = "langtut-tts"

# Flask Session
session_type = "filesystem"
session_permanent = false
session_use_signer = true
session_cookie_httponly = true
session_cookie_samesite = "Lax"

# Flask JSON
json_as_ascii = false
jsonify_mimetype = "application/json; charset=utf-8"

# Database
sqlalchemy_track_modifications = false

[local]
debug = true
session_cookie_secure = false
database_path = "data/app.db"

[production]
debug = false
session_cookie_secure = true
database_path = "/app/data/app.db"

[testing]
debug = false
session_cookie_secure = false
database_path = ":memory:"
tts_enabled = false
max_cards_per_session = 5

# Testing overrides
[testing.mock]
oauth_enabled = false
sheets_enabled = false
user_id = "test-user-123"
user_email = "test@example.com"
```

#### **Simplified `src/config.py`**
```python
# Single source of truth for all configuration
import os
import sys
import json
import tempfile
import logging
from pathlib import Path
from dynaconf import Dynaconf

def setup_logging():
    """Configure logging once"""
    # Current logging setup logic here
    pass

def get_environment() -> str:
    """Environment detection logic using Railway's automatic variables"""
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

def get_credentials_file(setting_key: str, env_var_key: str, default_file: str) -> str:
    """
    Get credentials file path with dual handling:
    - Local: Use file from settings
    - Production: Create temp file from environment variable
    """
    # Check for environment variable (production)
    env_var_content = settings.get(env_var_key, None)

    if env_var_content:
        # Production: Create temporary file from env var
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            if isinstance(env_var_content, str):
                credentials_data = json.loads(env_var_content)
            else:
                credentials_data = env_var_content

            json.dump(credentials_data, temp_file)
            return temp_file.name
    else:
        # Local: Use file from settings
        file_path = settings.get(setting_key, default_file)
        if Path(file_path).exists():
            return file_path
        return None

# Load configuration based on environment
environment = get_environment()
settings = Dynaconf(
    envvar_prefix='LANGTUT',
    settings_files=['settings.toml', '.secrets.toml'],
    environments=True,
    env=environment,
    load_dotenv=True,
)

# Initialize logging
logger = setup_logging()

# Export everything needed - no more individual imports
class Config:
    """Single configuration object"""

    # Environment
    ENVIRONMENT = environment
    DEBUG = settings.get('debug', False)

    # Core app
    SECRET_KEY = settings.get('SECRET_KEY', None)
    MAX_CARDS_PER_SESSION = settings.get('max_cards_per_session', 10)
    SPREADSHEET_ID = settings.get('spreadsheet_id')

    # Database
    DATABASE_PATH = settings.get('database_path')
    SQLALCHEMY_TRACK_MODIFICATIONS = settings.get('sqlalchemy_track_modifications', False)

    # Flask Session
    SESSION_TYPE = settings.get('session_type', 'filesystem')
    SESSION_PERMANENT = settings.get('session_permanent', False)
    SESSION_USE_SIGNER = settings.get('session_use_signer', True)
    SESSION_COOKIE_SECURE = settings.get('session_cookie_secure', False)
    SESSION_COOKIE_HTTPONLY = settings.get('session_cookie_httponly', True)
    SESSION_COOKIE_SAMESITE = settings.get('session_cookie_samesite', 'Lax')

    # Flask JSON
    JSON_AS_ASCII = settings.get('json_as_ascii', False)
    JSONIFY_MIMETYPE = settings.get('jsonify_mimetype', 'application/json; charset=utf-8')

    # Google OAuth - Dual credential handling
    CLIENT_SECRETS_FILE = get_credentials_file(
        'client_secrets_file',
        'CLIENT_SECRETS_JSON',
        'client_secret.json'
    )
    SCOPES = settings.get('scopes', [])
    API_SERVICE_NAME = settings.get('api_service_name', 'sheets')
    API_VERSION = settings.get('api_version', 'v4')

    # Google TTS - Dual credential handling
    TTS_ENABLED = settings.get('tts_enabled', True)
    TTS_LANGUAGE_CODE = settings.get('tts_language_code', 'pt-PT')
    TTS_VOICE_NAME = settings.get('tts_voice_name', 'pt-PT-Standard-A')
    TTS_AUDIO_ENCODING = settings.get('tts_audio_encoding', 'MP3')
    GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE = get_credentials_file(
        'google_cloud_service_account_file',
        'GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON',
        'google-cloud-service-account.json'
    )
    GCS_AUDIO_BUCKET = settings.get('gcs_audio_bucket', 'langtut-tts')

    # Testing mocks
    TESTING_MOCK_OAUTH = settings.get('mock.oauth_enabled', False) if environment == 'testing' else False
    TESTING_MOCK_SHEETS = settings.get('mock.sheets_enabled', False) if environment == 'testing' else False

# Export single config object
config = Config()
```

### **Credential Handling Strategy**

#### **Local Development** (`local` environment)
```toml
# settings.toml
[local]
client_secrets_file = "client_secret.json"
google_cloud_service_account_file = "google-cloud-service-account.json"
```

#### **Production** (`production` environment)
```bash
# Railway Environment Variables (already set)
LANGTUT_CLIENT_SECRETS_JSON='{"web":{"client_id":"...","client_secret":"..."}}'
LANGTUT_GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON='{"type":"service_account","project_id":"..."}'
LANGTUT_SECRET_KEY="your-secret-key"
```

#### **Testing** (`testing` environment)
```toml
# settings.toml
[testing]
tts_enabled = false
[testing.mock]
oauth_enabled = false
sheets_enabled = false
```

### **Environment Variables Update**

#### **Remove From Railway:**
- ❌ `LANGTUT_ENV` - Use Railway's automatic `RAILWAY_ENVIRONMENT=production`

#### **Keep in Railway:**
- ✅ `LANGTUT_CLIENT_SECRETS_JSON`
- ✅ `LANGTUT_GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON`
- ✅ `LANGTUT_SECRET_KEY`

### **Phase 3: Break Apart `src/__init__.py`**

#### **Problem with Current `__init__.py`**
- **Too much responsibility**: App creation, configuration, session setup, blueprint registration
- **Hard to test**: Everything happens at import time
- **Complex imports**: 25+ individual imports from config
- **Mixed concerns**: Configuration, initialization, and app factory all mixed together

#### **Solution: Split into Focused Files**

**1. `src/app_factory.py`** - Clean app creation
```python
"""Flask app factory"""
import os
from flask import Flask
from flask_session import Session

from src.config import config
from src.request_logger import setup_request_logging
from src.routes import register_blueprints
from src.utils import ensure_utf8_encoding

def create_app() -> Flask:
    """Create and configure Flask application"""

    # Set UTF-8 encoding
    ensure_utf8_encoding()

    # Create Flask app
    app = Flask(__name__, template_folder='../templates', static_folder='../static')

    # Configure app from unified config
    configure_app(app)

    # Initialize services
    initialize_services(app)

    return app

def configure_app(app: Flask) -> None:
    """Configure Flask app with settings"""
    app.secret_key = config.SECRET_KEY or os.urandom(24)

    # Session configuration
    app.config['SESSION_TYPE'] = config.SESSION_TYPE
    app.config['SESSION_PERMANENT'] = config.SESSION_PERMANENT
    app.config['SESSION_USE_SIGNER'] = config.SESSION_USE_SIGNER
    app.config['SESSION_COOKIE_SECURE'] = config.SESSION_COOKIE_SECURE
    app.config['SESSION_COOKIE_HTTPONLY'] = config.SESSION_COOKIE_HTTPONLY
    app.config['SESSION_COOKIE_SAMESITE'] = config.SESSION_COOKIE_SAMESITE

    # JSON configuration
    app.config['JSON_AS_ASCII'] = config.JSON_AS_ASCII
    app.config['JSONIFY_MIMETYPE'] = config.JSONIFY_MIMETYPE

def initialize_services(app: Flask) -> None:
    """Initialize all services"""

    # Initialize Flask-Session
    Session(app)

    # Set up request logging
    setup_request_logging(app)

    # Register blueprints
    register_blueprints(app)
```

**2. `src/database.py`** - Enhanced with environment-aware setup
```python
"""Database setup with environment awareness"""
import os
from flask_sqlalchemy import SQLAlchemy
from src.config import config

db = SQLAlchemy()

def init_database(app):
    """Initialize database with Flask app"""

    if config.ENVIRONMENT == 'testing':
        # Use in-memory database for testing
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    else:
        # Use file-based database
        if config.DATABASE_PATH.startswith('/'):
            database_path = config.DATABASE_PATH
        else:
            database_path = os.path.abspath(config.DATABASE_PATH)
            os.makedirs(os.path.dirname(database_path), exist_ok=True)

        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{database_path}'

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = config.SQLALCHEMY_TRACK_MODIFICATIONS
    db.init_app(app)

# Rest of database.py remains the same...
```

**3. `src/__init__.py`** - Minimal or eliminated
```python
"""Main app entry point"""
from src.app_factory import create_app

# Just export what's needed
__all__ = ['create_app']
```

**4. Updated `app.py`**
```python
"""Application entry point"""
from src.app_factory import create_app
from src.database import init_database
from src.config import config, logger

# Create app
app = create_app()

# Initialize database
init_database(app)

# No conditional logic needed - Gunicorn handles everything
```

### **Phase 4: Use Gunicorn Everywhere**

#### **Benefits of Gunicorn for Local Development**
- **Same execution path**: `app = create_app()` in all environments
- **No conditional logic**: Eliminates `if __name__ == '__main__'` complexity
- **Production parity**: Same WSGI server locally and in production
- **Better debugging**: Same behavior everywhere

#### **Gunicorn Configuration Files**

**Development Configuration** (`gunicorn.dev.conf.py`)
```python
# gunicorn.dev.conf.py
bind = "0.0.0.0:8080"
workers = 1
worker_class = "sync"
reload = True
reload_dirs = ["src", "templates", "static"]
reload_extra_files = ["settings.toml", ".secrets.toml"]
timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 50
preload_app = False
accesslog = "-"
errorlog = "-"
loglevel = "info"
capture_output = True
enable_stdio_inheritance = True
```

**Production Configuration** (`gunicorn.prod.conf.py`)
```python
# gunicorn.prod.conf.py
bind = "0.0.0.0:$PORT"
workers = 2
worker_class = "sync"
timeout = 120
keepalive = 2
max_requests = 1000
max_requests_jitter = 100
preload_app = True
accesslog = "-"
errorlog = "-"
loglevel = "info"
worker_tmp_dir = "/dev/shm"
```

#### **Development Commands**
```bash
# Local development with auto-reload
gunicorn --config gunicorn.dev.conf.py app:app

# Or with make command
make dev
```

#### **Optional: Development Scripts**
**`Makefile`**
```makefile
.PHONY: dev prod test clean

dev:
	gunicorn --config gunicorn.dev.conf.py app:app

prod:
	gunicorn --config gunicorn.prod.conf.py app:app

test:
	pytest

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
```

### **Phase 5: Railway Configuration**

#### **Keep `railway.toml` for Railway-Specific Settings**
You're absolutely right - `railway.toml` is needed for Railway deployment configuration. Railway automatically sets `RAILWAY_ENVIRONMENT=production`, so we only need to move `DATABASE_PATH` to `settings.toml`:

**Updated `railway.toml`** (Railway deployment config only)
```toml
[build]
builder = "nixpacks"

[deploy]
healthcheckPath = "/test"
healthcheckTimeout = 300
restartPolicyType = "on_failure"

# No [env] section needed - Railway automatically sets RAILWAY_ENVIRONMENT=production
# Move DATABASE_PATH to settings.toml
```

**Updated `Procfile`**
```bash
web: gunicorn --config gunicorn.prod.conf.py app:app
```

#### **Move DATABASE_PATH to `settings.toml`**
```toml
[production]
debug = false
session_cookie_secure = true
database_path = "/app/data/app.db"  # Moved from railway.toml
# Railway automatically sets RAILWAY_ENVIRONMENT=production - no need to set it manually
```

### **Implementation Plan (Updated)**

#### **Step 1: Environment Setup** (1 hour)
1. Update `settings.toml` with three environments
2. Enhance `src/config.py` with environment detection
3. Test environment detection works

#### **Step 2: Configuration Consolidation** (2 hours)
1. Move all config logic to unified `Config` class
2. Remove individual config imports from `__init__.py`
3. Test configuration loading

#### **Step 3: Break Apart `__init__.py`** (2 hours)
1. Create `src/app_factory.py` with clean app creation
2. Move database initialization logic to `src/database.py`
3. Simplify `src/__init__.py` to bare minimum
4. Update `app.py` to use new structure

#### **Step 4: Add Gunicorn Configuration** (1 hour)
1. Create `gunicorn.dev.conf.py` for local development
2. Create `gunicorn.prod.conf.py` for production
3. Update `Procfile` to use production config
4. Create `Makefile` for easy development commands
5. Test local development with Gunicorn

#### **Step 5: Testing Support** (1 hour)
1. Add testing environment configuration
2. Test that mocking works in testing environment
3. Create simple test to verify everything works

#### **Step 6: Cleanup** (30 minutes)
1. Remove `[env]` section from `railway.toml` and move `DATABASE_PATH` to `settings.toml` production section
2. Update any remaining imports
3. Test all functionality

**Total Time: ~7.5 hours**

### **Benefits of This Approach**

1. **Minimal risk** - Small, focused changes
2. **Clear environments** - Easy to understand and maintain
3. **Consolidated configuration** - Single source of truth
4. **Better structure** - No more god-file `__init__.py`
5. **Testing support** - Built-in mocking for tests
6. **Easy to debug** - Clear separation of concerns
7. **Gunicorn everywhere** - Same execution path, better development-production parity
8. **Railway compatibility** - Keeps necessary Railway deployment configuration

### **Development Workflow**

**Before:**
```bash
# Local development
python app.py

# Production (Railway)
gunicorn app:app
```

**After:**
```bash
# Local development
gunicorn --config gunicorn.dev.conf.py app:app
# or: make dev

# Production (Railway)
gunicorn --config gunicorn.prod.conf.py app:app

# Testing
pytest
# or: make test
```

### **Files Changed**
- ✏️ `settings.toml` - Enhanced with environments
- ✏️ `src/config.py` - Unified configuration
- ➕ `src/app_factory.py` - Clean app creation
- ✏️ `src/database.py` - Environment-aware database setup
- ✏️ `src/__init__.py` - Simplified to minimum
- ✏️ `app.py` - Simplified (no conditional logic)
- ✏️ `railway.toml` - Remove `[env]` section (keep deployment config)
- ✏️ `Procfile` - Use production Gunicorn config
- ➕ `gunicorn.dev.conf.py` - Local development configuration
- ➕ `gunicorn.prod.conf.py` - Production configuration
- ➕ `Makefile` - Development commands (optional)

### **Files Not Changed**
- All route files remain the same
- All service files remain the same
- All templates and static files remain the same
- No changes to core business logic
