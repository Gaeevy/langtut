# Windows Setup - Quick Fix

## The Problem You're Seeing

If you see this error:
```
ModuleNotFoundError: No module named 'fcntl'
```

**This is expected on Windows!** Gunicorn requires Unix-specific modules (`fcntl`) and will never work on Windows.

## The Solution (Pick One)

### Option 1: Use Waitress (Recommended) 🌟

Waitress is a production-quality WSGI server that works perfectly on Windows.

```powershell
# First, install the updated dependencies
uv sync

# Then run with Waitress
uv run waitress-serve --host=0.0.0.0 --port=8080 app:app
```

Or simply double-click: `run_windows.bat` (included in the repo)

### Option 2: Use Flask Development Server

Simpler, but less production-like:

```powershell
uv run python app.py
```

### Option 3: Use VSCode Debugger (Best for Development)

1. Open the project in VSCode
2. Go to Run and Debug panel (Ctrl+Shift+D)
3. Select **"Python: Debug App (Waitress - Windows)"** from the dropdown
4. Press F5

Now you can set breakpoints, step through code, and debug like normal!

## First Time Setup

Before running, initialize the database once:

```powershell
uv run python init_db.py
```

## Why This Happens

- **Gunicorn** = Unix/Linux/Mac only (uses `fcntl` module)
- **Waitress** = Cross-platform (pure Python)
- **Flask dev server** = Cross-platform but not for production

Railway deployment uses Gunicorn (because it runs on Linux), but local Windows development needs a different approach.

## Full Documentation

For complete setup instructions and troubleshooting, see:
- [Quick Start Guide](./docs/quick-start.md)
- [Windows Setup Guide](./docs/windows-setup-guide.md) (if it exists in your branch)

## Quick Reference

| Platform | Command |
|----------|---------|
| **Windows** | `uv run waitress-serve --host=0.0.0.0 --port=8080 app:app` |
| **Mac/Linux** | `uv run gunicorn --bind 0.0.0.0:8080 --workers 1 --reload app:app` |
| **Any (Debug)** | `uv run python app.py` |

All commands:
- Initialize database properly ✅
- Enable debugging/auto-reload ✅
- Run on http://localhost:8080 ✅
- Work with the `app:app` pattern ✅
