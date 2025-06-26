# Language Learning Flashcard App

A simple Flask web application that integrates with Google Sheets to provide ANKI-style language learning flashcards with European Portuguese text-to-speech.

## Features

- Reads vocabulary and translations directly from a Google Spreadsheet
- Shows flashcards to users one by one
- Tracks correct/incorrect answers
- Updates statistics (times shown, correct answers, last shown) back to the spreadsheet
- **European Portuguese Text-to-Speech** using Google Cloud TTS
  - Automatic pronunciation on feedback pages
  - Manual controls for word and example pronunciation
  - Audio caching for improved performance
  - Multiple voice options available
- Simple, responsive UI
- Progressive Web App (PWA) support for mobile devices

## Setup Instructions

### Prerequisites

- Python 3.11 or higher
- Poetry for dependency management

### Installation

1. Clone this repository
2. Install dependencies using Poetry:

```bash
poetry install
```

3. Run the application:

```bash
poetry run python app.py
```

4. Open your browser and navigate to http://127.0.0.1:5000

**Note**: The `requirements.txt` file is maintained for Railway deployment. For local development, use Poetry as shown above.

### Google Sheets Setup

The application connects to a public Google Sheet where the data is stored. The sheet should be structured as follows:

- Column A: id (unique identifier for the card)
- Column B: word (the word in the language being learned)
- Column C: translation
- Column D: equivalent (translation in another language or additional info)
- Column E: example (example sentence using the word)
- Column F: cnt_shown (counter for how many times the card was shown)
- Column G: cnt_corr_answers (counter for how many times the card was answered correctly)
- Column H: last_shown (timestamp of when the card was last shown)

The default sheet used in this application is:
https://docs.google.com/spreadsheets/d/15_PsHfMb440wtUgZ0d1aJmu5YIXoo9JKytlJINxOV8Q

To use your own sheet, update the `SPREADSHEET_ID` and `SHEET_NAME` in the `app.py` file.

### Setting up Google OAuth Authentication (Optional)

By default, the application can read public Google Sheets but cannot write back to them. If you want to enable writing back statistics to the sheet, you need to set up Google OAuth:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable the Google Sheets API for your project
4. Create OAuth 2.0 credentials:
   - Go to "Credentials" in the left sidebar
   - Click "Create Credentials" → "OAuth client ID"
   - Select "Web application" as the application type
   - Add `http://localhost:5000/oauth2callback` as an authorized redirect URI
   - Click "Create"
5. Download the client secret JSON file
6. Rename it to `client_secret.json` and place it in the root directory of this project

After setting up the credentials, users will be able to authenticate with their Google account and allow the app to modify their sheets.

### Setting up Text-to-Speech (Optional)

The application supports European Portuguese text-to-speech using Google Cloud TTS. To enable this feature:

1. **Enable Google Cloud TTS API** in your Google Cloud project
2. **Create a service account** with "Cloud Text-to-Speech User" role
3. **Download the service account key** as JSON
4. **Configure the application**:
   - For local development: Save the key as `google-cloud-service-account.json` in the project root
   - For production: Set the `LANGTUT_GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON` environment variable

For detailed setup instructions, see [TTS_SETUP.md](TTS_SETUP.md).

**Note**: Google Cloud TTS requires a billing account, but offers 1 million characters free per month. Typical usage costs are very low (around $0.14 per 1000 cards).

## Usage

1. Click "Start Learning" on the homepage
2. The application will load cards from the spreadsheet
3. For each card, type your answer and click "Submit"
4. You'll receive feedback on whether your answer was correct
5. Continue through all cards
6. At the end, view your results and statistics

## Limitations

This is an MVP (Minimum Viable Product) with the following limitations:

- Works with public Google Sheets only (read-only without authentication)
- Simple answer matching (exact match only)
- No user accounts or personalized learning paths
- Limited error handling for Google Sheets API issues
- Writing back to the spreadsheet requires Google OAuth authentication

## Future Improvements

- Automatic setup of OAuth credentials
- Multiple language support
- Spaced repetition algorithm
- More sophisticated answer checking
- Custom card decks for different topics

## Project Structure

The project follows a modular structure with key components divided into separate files:

- `app.py` - Main entry point for the application
- `src/` - Source code directory
  - `__init__.py` - Initializes the Flask application
  - `auth.py` - Authentication utilities for Google OAuth
  - `config.py` - Configuration management using Dynaconf
  - `gsheet.py` - Google Sheets interaction functions
  - `models.py` - Data models using Pydantic
  - `routes.py` - Flask routes and request handlers
- `settings.toml` - Main configuration file
- `.secrets.toml` - Secret configuration values (not committed to Git)
- `templates/` - HTML templates
- `static/` - Static assets (CSS, JavaScript)

## Configuration

The application uses Dynaconf for configuration management, allowing for:

- Different environments (development, production)
- Sensitive information separation
- Environment variable overrides

### Configuration Files

- `settings.toml` - Contains default non-sensitive configuration
- `.secrets.toml` - Contains sensitive configuration (not in Git)
- `.secrets.toml.example` - Template for creating your secrets file

To set up your configuration:

1. Copy `.secrets.toml.example` to `.secrets.toml`
2. Generate a secret key and update the configuration:
   ```bash
   python -c "import os; print(os.urandom(24).hex())"
   ```
3. Edit `.secrets.toml` with your sensitive configuration values

### Environment Variables

You can override any configuration value using environment variables with the `LANGTUT_` prefix. For example:

```bash
export LANGTUT_DEBUG=false
```
