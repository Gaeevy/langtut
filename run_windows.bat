@echo off
REM Language Tutor - Windows Development Server
REM This script uses Waitress (Windows-compatible WSGI server)

echo.
echo ========================================
echo   Language Tutor - Development Server
echo   (Windows - using Waitress)
echo ========================================
echo.
echo Starting server on http://localhost:8080
echo Press Ctrl+C to stop the server
echo.

REM Run with uv (automatically activates virtual environment)
uv run waitress-serve --host=0.0.0.0 --port=8080 app:app
