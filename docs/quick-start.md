# Quick Start Guide for New Developers

## Running the Application Locally

### ✅ CORRECT Way to Run

#### On macOS/Linux:

```bash
uv run gunicorn --bind 0.0.0.0:8080 --workers 1 --reload app:app
```

#### On Windows:

**Important:** Gunicorn doesn't work on Windows (requires Unix-specific `fcntl` module). Use Waitress instead:

```bash
uv run waitress-serve --host=0.0.0.0 --port=8080 app:app
```

Or use Flask's built-in server (simpler, but less production-like):

```bash
uv run python app.py
```

**Why these commands work:**
1. Import the `app` variable from `app.py` module
2. Properly initializes the Flask app via `create_app()`
3. **Initializes the database** with `init_database(app)`
4. Sets up environment-specific configuration
5. Enable auto-reload for development (Gunicorn/Waitress) or debug mode (Flask)

### ❌ INCORRECT Ways to Run

**Don't do these:**

```bash
# ❌ Don't run directly (missing database init)
python app.py

# ❌ Don't run via src module (no database binding)
python -m src

# ❌ Don't use Flask's dev server (use Gunicorn consistently)
flask run
```

## Application Architecture

### App Creation Flow

```
app.py (ENTRY POINT)
  ↓
  calls create_app() from src/__init__.py
  ↓
  Flask app instance created
  ↓
  init_database(app) called - SQLAlchemy bound to app
  ↓
  App ready for Gunicorn
```

### Key Files

- **`app.py`** - Entry point that Gunicorn uses
- **`src/__init__.py`** - Contains `create_app()` factory function
- **`src/database.py`** - SQLAlchemy models and database functions

### Why This Pattern?

The **Application Factory Pattern** keeps the app modular:
- `create_app()` builds the Flask app (routes, config, extensions)
- `app.py` handles environment-specific initialization (database, logging, OAuth setup)
- Gunicorn imports the fully-initialized `app` object

## Database Initialization

### First Time Setup

If you get a SQLAlchemy error like:
```
Login error: The current Flask app is not registered with this 'SQLAlchemy' instance.
```

Run the database initialization script:

```bash
uv run python init_db.py
```

This will:
- Create the `data/` directory
- Create `data/app.db` SQLite database
- Create all tables (users, user_spreadsheets)
- Verify the setup

### How Database Init Works

1. **`app.py` calls `init_database(app)`** (line 30)
   - Sets `SQLALCHEMY_DATABASE_URI`
   - Calls `db.init_app(app)` to bind SQLAlchemy to Flask

2. **First database operation calls `ensure_tables()`**
   - Checks if tables exist
   - Creates them if needed using `db.create_all()`

3. **All database operations require app context**
   - Gunicorn provides this automatically
   - Manual scripts need `with app.app_context():`

## Common Issues

### Issue: SQLAlchemy Not Registered

**Symptom:**
```
RuntimeError: The current Flask app is not registered with this 'SQLAlchemy' instance.
```

**Cause:** Running the app without proper database initialization

**Fix:**
1. Always use `uv run gunicorn ...` command (not direct Python)
2. If testing, run `uv run python init_db.py` first

### Issue: Import Errors

**Symptom:**
```
ModuleNotFoundError: No module named 'src'
```

**Cause:** Not using `uv run` or wrong working directory

**Fix:** Always prefix commands with `uv run` from project root

### Issue: OAuth Errors Locally

**Symptom:**
```
oauthlib.oauth2.rfc6749.errors.InsecureTransportError
```

**Fix:** `app.py` automatically sets `OAUTHLIB_INSECURE_TRANSPORT=1` in local mode

## Development Workflow

### Standard Development Loop

```bash
# 1. Start development server
uv run gunicorn --bind 0.0.0.0:8080 --workers 1 --reload app:app

# 2. Open browser to http://localhost:8080

# 3. Make code changes - server auto-reloads

# 4. Run tests
uv run pytest

# 5. Check code quality
uv run pre-commit run --all-files
```

### VSCode Debugging 🐛

The project includes VSCode debug configurations in `.vscode/launch.json`. To debug:

#### Option 1: Debug with Gunicorn (Mac/Linux - Production-like)
1. Open VSCode's Run and Debug panel (Ctrl+Shift+D / Cmd+Shift+D)
2. Select **"Python: Debug App (Gunicorn - Unix/Mac)"** from the dropdown
3. Press F5 or click the green play button
4. Set breakpoints anywhere in your code
5. App runs at `http://localhost:8080` with full debugger support

**Benefits:**
- Same environment as production (Gunicorn)
- Full breakpoint support
- Auto-reload on code changes
- Step through code, inspect variables, evaluate expressions

#### Option 2: Debug with Waitress (Windows - Production-like)
1. Select **"Python: Debug App (Waitress - Windows)"**
2. Press F5
3. Uses Waitress WSGI server (Windows-compatible alternative to Gunicorn)

**Benefits:**
- Works on Windows (no `fcntl` dependency)
- Production-quality WSGI server
- Full debugging support
- Similar to Gunicorn's behavior

#### Option 3: Debug with Flask Dev Server (All platforms - Fastest)
1. Select **"Python: Debug App (Direct - Faster)"**
2. Press F5
3. Uses Flask's built-in server (works everywhere)

**Benefits:**
- Faster startup time
- Simpler stack traces
- Works on Windows, Mac, Linux
- Good for quick debugging sessions

#### Other Debug Configurations

**Init Database:**
- Select **"Python: Init Database"**
- Debug the database initialization process

**Test Current File:**
- Open any test file
- Select **"Python: Test Current File"**
- Debug specific tests with breakpoints

**Test All:**
- Select **"Python: Test All"**
- Run entire test suite with debugging

### Windows Users - Important! 🪟

#### Problem 1: Gunicorn doesn't work on Windows

If you see this error:
```
ModuleNotFoundError: No module named 'fcntl'
```

**Solution:** Gunicorn requires Unix-specific modules. On Windows, use one of these instead:

1. **Waitress** (Recommended - production-quality WSGI server):
   ```bash
   uv run waitress-serve --host=0.0.0.0 --port=8080 app:app
   ```
   Or use the VSCode debug config: **"Python: Debug App (Waitress - Windows)"**

2. **Flask Dev Server** (Simpler, faster startup):
   ```bash
   uv run python app.py
   ```
   Or use the VSCode debug config: **"Python: Debug App (Direct - Faster)"**

#### Problem 2: VSCode defaults to `flask run`

If you see this in your debug terminal:
```powershell
w:\Python\langtut\.venv\Scripts\python.exe -m flask run
```

**Don't use `flask run` directly!** It bypasses the database initialization in `app.py`.

**Solution:** Use the provided launch configurations instead (they handle everything correctly).

### Debugging Tips

**Set Breakpoints:**
- Click left of line number to add breakpoint
- Red dot appears when breakpoint is active
- Code pauses when breakpoint is hit

**Debug Console:**
- Evaluate expressions while paused
- Inspect variables: `user`, `config.DEBUG`, etc.
- Call functions: `db.session.query(User).count()`

**Step Through Code:**
- F10: Step over (execute current line)
- F11: Step into (enter function)
- Shift+F11: Step out (exit current function)
- F5: Continue to next breakpoint

**Watch Variables:**
- Add variables to Watch panel
- See values update as code executes

### Testing Database Changes

```bash
# Reset database (be careful - deletes all data!)
rm data/app.db

# Reinitialize
uv run python init_db.py

# Start app
uv run gunicorn --bind 0.0.0.0:8080 --workers 1 --reload app:app
```

## Environment Configuration

### Required Files

- `settings.toml` - Main configuration (in git)
- `.secrets.toml` - Sensitive data (NOT in git, create from template)
- `client_secret.json` - Google OAuth credentials (NOT in git)

### Environment Variables

Can override any setting via environment variables:

```bash
# Example: Change database location
export LANGTUT_DATABASE_PATH=/tmp/test.db

# Example: Enable debug mode
export LANGTUT_DEBUG=true
```

Prefix all environment variables with `LANGTUT_`.

## Next Steps

1. ✅ Read [docs/architecture.md](./architecture.md) for system design
2. ✅ Read [docs/development-guide.md](./development-guide.md) for detailed dev info
3. ✅ Review [Cursor Rules](../.cursorrules) for coding standards
4. ✅ Set up Google OAuth credentials and spreadsheet access

## Getting Help

If you encounter issues:
1. Check logs - Gunicorn shows detailed startup info
2. Verify configuration - `uv run python -c "from src.config import config; print(config.DEBUG)"`
3. Test database - `uv run python init_db.py`
4. Review error templates - `templates/error.html`
