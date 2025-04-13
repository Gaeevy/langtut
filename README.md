# Language Learning Flashcard App

A simple Flask web application that integrates with Google Sheets to provide ANKI-style language learning flashcards.

## Features

- Reads vocabulary and translations directly from a Google Spreadsheet
- Shows flashcards to users one by one
- Tracks correct/incorrect answers
- Updates statistics (times shown, correct answers, last shown) back to the spreadsheet
- Simple, responsive UI

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