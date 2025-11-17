# Windows Developer Setup Guide

A step-by-step guide for new Windows developers to get started with the Language Learning Flashcard App.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Install Python](#install-python)
3. [Install UV Package Manager](#install-uv-package-manager)
4. [Clone the Repository](#clone-the-repository)
5. [Project Configuration](#project-configuration)
6. [Initialize the Environment](#initialize-the-environment)
7. [Run the Application](#run-the-application)
8. [Development Tools](#development-tools)
9. [Troubleshooting](#troubleshooting)

## Prerequisites

Before you begin, ensure you have:
- **Windows 10 or later** (64-bit)
- **Git for Windows** - [Download here](https://git-scm.com/download/win)
- **Administrator access** for installing software
- **Google Cloud account** (for OAuth and TTS services)
- **Google Sheet** with vocabulary data (or create one)

## Install Python

### Step 1: Download Python

1. Visit the official Python website: https://www.python.org/downloads/
2. Download **Python 3.11 or later** (recommended: Python 3.11.x)
3. Run the installer

### Step 2: Install Python

**IMPORTANT**: During installation:
- ✅ **Check "Add Python to PATH"** (critical!)
- ✅ Select "Install for all users" (recommended)
- ✅ Click "Install Now"

### Step 3: Verify Installation

Open **Command Prompt** or **PowerShell** and run:

```powershell
python --version
```

You should see output like: `Python 3.11.x`

If you get an error, you may need to use `py` instead:

```powershell
py --version
```

## Install UV Package Manager

UV is a fast Python package manager (10-100x faster than pip/poetry). This project **requires UV** for all development tasks.

### Step 1: Install UV

Open **PowerShell** as Administrator and run:

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Alternative method** (if the above doesn't work):

```powershell
pip install uv
```

### Step 2: Verify UV Installation

```powershell
uv --version
```

You should see output like: `uv 0.x.x`

### Step 3: Add UV to PATH (if needed)

If `uv` command is not found, add it to your PATH:

1. Open **Environment Variables**:
   - Press `Win + R`
   - Type `sysdm.cpl` and press Enter
   - Go to **Advanced** tab → **Environment Variables**

2. Under **User variables**, find `Path` and click **Edit**

3. Add the UV installation directory:
   - Typically: `C:\Users\YourUsername\.cargo\bin`

4. Click **OK** and restart PowerShell

## Clone the Repository

### Step 1: Open Terminal

Open **PowerShell** or **Command Prompt** in your preferred directory:

```powershell
# Navigate to your projects directory
cd C:\Users\YourUsername\Projects
```

### Step 2: Clone the Repository

```powershell
git clone <repository-url>
cd langtut
```

Replace `<repository-url>` with the actual repository URL.

## Project Configuration

### Step 1: Create Configuration Files

The project requires two configuration files:

#### Create `settings.toml`

This file should already exist. Verify it's present:

```powershell
dir settings.toml
```

#### Create `.secrets.toml`

Create a new file called `.secrets.toml` in the project root:

```powershell
New-Item -Path .secrets.toml -ItemType File
```

Edit `.secrets.toml` and add your sensitive configuration:

```toml
[default]
# Flask Configuration
SECRET_KEY = "your-secret-key-here-generate-a-random-string"

# Google OAuth Credentials
GOOGLE_CLIENT_ID = "your-client-id.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "your-client-secret"

# Google Cloud Service Account (for Sheets API)
GOOGLE_CLOUD_PROJECT = "your-project-id"
GOOGLE_CLOUD_CREDENTIALS_FILE = "google-cloud-service-account.json"

# Optional: Override settings
DEBUG = true
PORT = 8080
```

**IMPORTANT**: Never commit `.secrets.toml` to git! It's already in `.gitignore`.

### Step 2: Google Cloud Setup

#### OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable **Google+ API** and **Google Sheets API**
4. Go to **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
5. Set application type to **Web application**
6. Add authorized redirect URIs:
   - `http://localhost:8080/oauth2callback`
   - `http://127.0.0.1:8080/oauth2callback`
7. Download the credentials and save as `client_secret.json` in the project root

#### Service Account (for Sheets API)

1. In Google Cloud Console, go to **Credentials**
2. Click **Create Credentials** → **Service Account**
3. Create the service account and download the JSON key
4. Save it as `google-cloud-service-account.json` in the project root
5. Share your Google Sheet with the service account email (found in the JSON file)

### Step 3: Verify Configuration Files

```powershell
dir client_secret.json
dir google-cloud-service-account.json
dir .secrets.toml
```

All three files should exist in your project root.

## Initialize the Environment

### Step 1: Sync Dependencies

UV will automatically create a virtual environment and install all dependencies:

```powershell
uv sync
```

This command:
- Creates a `.venv` directory with a virtual environment
- Installs all dependencies from `pyproject.toml` and `uv.lock`
- Takes ~10-30 seconds (much faster than pip!)

### Step 2: Verify Installation

Check that dependencies are installed:

```powershell
uv pip list
```

You should see packages like Flask, SQLAlchemy, google-auth, etc.

### Step 3: Initialize Database

The database will be created automatically on first run, but you can verify:

```powershell
uv run python -c "from src.database import db; print('Database OK')"
```

## Run the Application

### Development Server (Recommended)

Run the application with hot-reload:

```powershell
uv run gunicorn --bind 0.0.0.0:8080 --workers 1 --reload app:app
```

**What this does**:
- Starts the Flask application
- Listens on `http://localhost:8080`
- Auto-reloads when you change code
- Shows detailed logs in the terminal

### Alternative: Direct Python Execution

For quick testing (not recommended for development):

```powershell
uv run python app.py
```

### Access the Application

1. Open your browser
2. Navigate to: `http://localhost:8080`
3. You should see the login page

### First-Time Setup

1. Click **Sign in with Google**
2. Authorize the application
3. Configure your Google Sheet URL in settings
4. Start learning!

## Development Tools

### Run Tests

```powershell
uv run pytest
```

### Code Quality Checks

Install pre-commit hooks:

```powershell
uv run pre-commit install
```

Run checks manually:

```powershell
uv run pre-commit run --all-files
```

### View Dependency Tree

```powershell
uv tree
```

### Check Configuration

```powershell
uv run python -c "from src.config import config; print(f'Debug: {config.DEBUG}, Port: {config.PORT}')"
```

### Test TTS Service

```powershell
uv run python -c "from src.tts_service import tts_service; print(tts_service.generate_audio('Olá'))"
```

## Troubleshooting

### Common Windows Issues

#### Issue: `uv: command not found`

**Solution**: UV not in PATH. Reinstall or add to PATH manually:

```powershell
# Check if UV is installed
pip show uv

# If not found, reinstall
pip install uv
```

#### Issue: `python: command not found`

**Solution**: Python not in PATH. Use `py` instead:

```powershell
# Instead of: uv run python app.py
# Use:
py -m uv run python app.py
```

Or reinstall Python with "Add to PATH" option checked.

#### Issue: Permission Denied Errors

**Solution**: Run PowerShell as Administrator:

1. Right-click **PowerShell**
2. Select **Run as Administrator**

#### Issue: Script Execution Policy Error

If you see: `cannot be loaded because running scripts is disabled`

**Solution**: Enable script execution:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### Issue: Port 8080 Already in Use

**Solution**: Either:

1. Stop the application using port 8080
2. Or use a different port:

```powershell
uv run gunicorn --bind 0.0.0.0:8081 --workers 1 --reload app:app
```

Update your `.secrets.toml`:

```toml
PORT = 8081
```

#### Issue: Google Sheets API Errors

**Solution**:

1. Verify service account JSON is correct
2. Share your Google Sheet with the service account email
3. Check that the Sheet URL is configured in app settings

#### Issue: OAuth Redirect URI Mismatch

**Solution**: In Google Cloud Console:

1. Go to **Credentials** → Your OAuth Client
2. Add redirect URIs:
   - `http://localhost:8080/oauth2callback`
   - `http://127.0.0.1:8080/oauth2callback`
   - If using different port, add that too

### Getting Help

If you encounter issues:

1. Check the logs in your terminal
2. Review the [main README.md](../README.md)
3. Check other documentation in the [docs/](.) directory
4. Search for similar issues in the project's issue tracker

## Next Steps

Now that you have the application running:

1. **Read the Documentation**:
   - [Architecture Guide](architecture.md) - Understand the system design
   - [Development Guide](development-guide.md) - Learn development workflows
   - [TTS System](tts-system.md) - Text-to-speech implementation
   - [Listening Mode](listening-mode.md) - Audio-first learning feature

2. **Explore the Code**:
   - Review the project structure in [.cursorrules](../.cursorrules)
   - Understand the blueprint pattern in `src/routes/`
   - Check out the session management in `src/session_manager.py`

3. **Start Developing**:
   - Make small changes and see hot-reload in action
   - Run tests with `uv run pytest`
   - Use pre-commit hooks to maintain code quality

4. **Windows-Specific Tips**:
   - Use **PowerShell** or **Windows Terminal** for better experience
   - Consider using **VS Code** with Python extension
   - Install **WSL2** for a more Unix-like environment (optional)

## Quick Reference

```powershell
# Start development server
uv run gunicorn --bind 0.0.0.0:8080 --workers 1 --reload app:app

# Run tests
uv run pytest

# Code quality checks
uv run pre-commit run --all-files

# View dependencies
uv pip list
uv tree

# Update dependencies
uv sync

# Check configuration
uv run python -c "from src.config import config; print(config.DEBUG)"
```

---

**Welcome to the team! Happy coding! 🚀**
