from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_cors import CORS
from flask_session import Session  # Import Flask-Session
import os
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json
import requests
import csv
from io import StringIO
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
import pathlib

app = Flask(__name__)
# Disable CORS for local development
# CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
app.secret_key = os.urandom(24)  # For session management

# Add session configuration for better cookie handling
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Initialize Flask-Session
Session(app)

# Google Sheets API settings
SPREADSHEET_ID = '15_PsHfMb440wtUgZ0d1aJmu5YIXoo9JKytlJINxOV8Q'
SHEET_NAME = 'Sheet1'  # Adjust this to your sheet's name

# Google OAuth2 settings
CLIENT_SECRETS_FILE = 'client_secret.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
API_SERVICE_NAME = 'sheets'
API_VERSION = 'v4'

# Load registered redirect URIs from client_secret.json
try:
    with open(CLIENT_SECRETS_FILE, 'r') as f:
        client_secret_data = json.load(f)
        REGISTERED_REDIRECT_URIS = client_secret_data.get('web', {}).get('redirect_uris', [])
        print(f"Registered redirect URIs: {REGISTERED_REDIRECT_URIS}")
except Exception as e:
    print(f"Error loading redirect URIs from client_secret.json: {e}")
    REGISTERED_REDIRECT_URIS = []

# Pydantic model for language cards
class Card(BaseModel):
    id: int
    word: str
    translation: str
    equivalent: str
    example: str
    cnt_shown: int = 0
    cnt_corr_answers: int = 0
    last_shown: Optional[str] = None

def get_credentials():
    """Get valid credentials from session or through the OAuth flow."""
    creds = None
    
    # Load credentials from session if available
    if 'credentials' in session:
        creds = Credentials(**session['credentials'])
    
    # Check if credentials are expired and refresh if needed
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        session['credentials'] = credentials_to_dict(creds)
    
    return creds

def credentials_to_dict(credentials):
    """Convert credentials object to dictionary for session storage."""
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

def get_worksheet():
    """Connect to Google Sheets using gspread"""
    # Try to get authenticated access first
    creds = get_credentials()
    if creds:
        try:
            # Authenticated access
            gc = gspread.authorize(creds)
            sh = gc.open_by_key(SPREADSHEET_ID)
            worksheet = sh.worksheet(SHEET_NAME)
            return worksheet, True  # Second value indicates if write is possible
        except Exception as e:
            print(f"Error accessing spreadsheet with auth: {e}")
    
    # Fall back to read-only access for public sheets
    try:
        # For an MVP, we'll use a simpler approach with direct HTTP requests
        # This works for public sheets that are published to the web
        # Get the published CSV version of the sheet
        sheet_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv"
        response = requests.get(sheet_url)
        
        if response.status_code == 200:
            # We got the CSV data, but we need to parse it and return a mock worksheet
            csv_data = StringIO(response.text)
            reader = csv.reader(csv_data)
            rows = list(reader)
            
            # Create a simple mock worksheet object that has get_all_values method
            class MockWorksheet:
                def get_all_values(self):
                    return rows
                
                def batch_update(self, updates):
                    # Cannot update without authentication
                    print("Warning: Can't update sheet without authentication")
                    return False
            
            return MockWorksheet(), False  # Second value indicates if write is not possible
        else:
            print(f"Error fetching spreadsheet: {response.status_code}")
            return None, False
    except Exception as e:
        print(f"Error accessing spreadsheet: {e}")
        return None, False

def read_spreadsheet():
    """Read data from Google Sheets"""
    worksheet, _ = get_worksheet()
    if not worksheet:
        return []
    
    # Get all values from the worksheet
    values = worksheet.get_all_values()
    
    if not values:
        return []
    
    # Skip the header row
    data_rows = values[1:]
    cards = []
    
    for row in data_rows:
        if not row or len(row) < 5 or not row[0]:  # Skip empty rows
            continue
        
        # Pad the row if it doesn't have enough columns
        padded_row = row + ['0'] * (8 - len(row)) if len(row) < 8 else row
        
        try:
            card = Card(
                id=int(padded_row[0]),
                word=padded_row[1],
                translation=padded_row[2] if len(padded_row) > 2 else "",
                equivalent=padded_row[3] if len(padded_row) > 3 else "",
                example=padded_row[4] if len(padded_row) > 4 else "",
                cnt_shown=int(padded_row[5]) if len(padded_row) > 5 and padded_row[5] else 0,
                cnt_corr_answers=int(padded_row[6]) if len(padded_row) > 6 and padded_row[6] else 0,
                last_shown=padded_row[7] if len(padded_row) > 7 and padded_row[7] else None
            )
            cards.append(card)
        except Exception as e:
            print(f"Error processing row {row}: {e}")
            continue
    
    return cards

def update_spreadsheet(cards):
    """Update data in Google Sheets in bulk"""
    worksheet, can_write = get_worksheet()
    if not worksheet:
        raise Exception("Could not access spreadsheet")
    
    if not can_write:
        raise Exception("Authentication required to update spreadsheet")
    
    # Prepare the data for update
    values = []
    for card in cards:
        values.append([
            card.id,
            card.word,
            card.translation,
            card.equivalent,
            card.example,
            card.cnt_shown,
            card.cnt_corr_answers,
            card.last_shown
        ])
    
    # Update the spreadsheet (starting from row 2 to skip header)
    # For gspread, we need to update the cells with batch update
    cell_updates = []
    for i, row in enumerate(values):
        for j, value in enumerate(row):
            cell_updates.append({
                'range': f'{chr(65+j)}{i+2}',  # e.g., A2, B2, etc.
                'values': [[value]]
            })
    
    # Execute the batch update
    result = worksheet.batch_update(cell_updates)
    
    return result

@app.route('/')
def index():
    # Print debug information
    print("Index route accessed")
    print(f"Session data: {session}")
    
    # Check if session is working
    if 'test' not in session:
        session['test'] = 'Session is working'
    
    # Check authentication status
    is_authenticated = 'credentials' in session
    print(f"Authentication status: {is_authenticated}")
    
    return render_template('index.html', is_authenticated=is_authenticated)

@app.route('/auth')
def auth():
    """Initiate the OAuth flow to authorize the application."""
    try:
        # Get the current request URL and determine which port we're using
        current_url = request.url
        print(f"Auth request URL: {current_url}")
        parts = request.host.split(':')
        port = parts[1] if len(parts) > 1 else '8080'  # default to 8080 if no port specified
        
        # Use the first registered redirect URI if available
        if REGISTERED_REDIRECT_URIS:
            # Find a URI that matches our current port
            matching_uris = [uri for uri in REGISTERED_REDIRECT_URIS if f":{port}" in uri]
            if matching_uris:
                redirect_uri = matching_uris[0]
            else:
                # Fall back to the first registered URI
                redirect_uri = REGISTERED_REDIRECT_URIS[0]
        else:
            # No registered URIs found, create a default one
            redirect_uri = f'http://localhost:{port}/oauth2callback'
        
        print(f"Using registered redirect URI for auth: {redirect_uri}")
        
        # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, scopes=SCOPES,
            redirect_uri=redirect_uri)
        
        # Generate URL for request to Google's OAuth 2.0 server
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true')
        
        # Store the state and redirect URI for later verification
        session['state'] = state
        session['redirect_uri'] = redirect_uri
        
        print(f"Authorization URL: {authorization_url}")
        return redirect(authorization_url)
    except Exception as e:
        print(f"Authentication error: {str(e)}")
        return render_template('error.html', message=f"Authentication error: {str(e)}")

@app.route('/oauth2callback')
def oauth2callback():
    """Callback function for the OAuth flow."""
    # Print detailed debug information
    print("\n--- OAuth Callback Debug Info ---")
    print(f"Request URL: {request.url}")
    print(f"Request Args: {request.args}")
    print(f"Session Data: {session}")
    print("--------------------------------\n")
    
    # Ensure that the request is not a forgery and that the user sending
    # this connect request is the expected user
    state = session.get('state')
    
    if not state or state != request.args.get('state'):
        return render_template('error.html', message="Invalid state parameter")
    
    # Use the authorization server's response to fetch the OAuth 2.0 tokens
    try:
        # Use the same redirect URI that was used for the initial auth request
        redirect_uri = session.get('redirect_uri')
        if not redirect_uri:
            # Fallback if we don't have it in the session
            print("Warning: No redirect_uri in session, constructing one...")
            parts = request.host.split(':')
            host = parts[0]  # localhost or 127.0.0.1
            port = parts[1] if len(parts) > 1 else '8080'  # default to 8080 if no port specified
            redirect_uri = f'http://localhost:{port}/oauth2callback'
        
        print(f"Using redirect URI for callback: {redirect_uri}")
        
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, scopes=SCOPES,
            state=state,
            redirect_uri=redirect_uri)
        
        # Get the authorization response from the request
        authorization_response = request.url
        print(f"Authorization response: {authorization_response}")
        
        flow.fetch_token(authorization_response=authorization_response)
        
        # Store credentials in the session
        credentials = flow.credentials
        session['credentials'] = credentials_to_dict(credentials)
        
        return redirect(url_for('index'))
    except Exception as e:
        print(f"OAuth callback error: {str(e)}")
        return render_template('error.html', message=f"OAuth callback error: {str(e)}")

@app.route('/clear')
def clear_credentials():
    """Clear the stored credentials."""
    if 'credentials' in session:
        del session['credentials']
    return redirect(url_for('index'))

@app.route('/start', methods=['POST'])
def start_learning():
    # Read cards from spreadsheet
    cards = read_spreadsheet()
    if not cards:
        return render_template('error.html', message='No cards found in the spreadsheet')
    
    # Store cards in session (converted to dict for JSON serialization)
    session['cards'] = [card.model_dump() for card in cards]
    session['current_index'] = 0
    session['answers'] = []
    
    # Redirect to the first card
    return redirect(url_for('show_card'))

@app.route('/card')
def show_card():
    if 'cards' not in session or 'current_index' not in session:
        return redirect(url_for('index'))
    
    cards = session['cards']
    index = session['current_index']
    
    if index >= len(cards):
        # All cards have been shown, go to results
        return redirect(url_for('show_results'))
    
    current_card = cards[index]
    return render_template('card.html', card=current_card, index=index, total=len(cards))

@app.route('/answer', methods=['POST'])
def process_answer():
    if 'cards' not in session or 'current_index' not in session:
        return redirect(url_for('index'))
    
    # Get user's answer
    user_answer = request.form.get('answer', '').strip().lower()
    
    # Get current card
    cards = session['cards']
    index = session['current_index']
    current_card = cards[index]
    
    # Check if answer is correct (simple exact match for MVP)
    correct = user_answer == current_card['word'].lower() or \
              user_answer == current_card['translation'].lower() or \
              user_answer == current_card['equivalent'].lower()
    
    # Update card stats
    current_card['cnt_shown'] += 1
    if correct:
        current_card['cnt_corr_answers'] += 1
    current_card['last_shown'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Store updated card back to session
    cards[index] = current_card
    session['cards'] = cards
    
    # Record the answer
    session['answers'] = session.get('answers', []) + [{
        'card_id': current_card['id'],
        'correct': correct,
        'user_answer': user_answer
    }]
    
    # Move to next card
    session['current_index'] = index + 1
    
    return redirect(url_for('show_feedback', correct=str(correct).lower()))

@app.route('/feedback/<correct>')
def show_feedback(correct):
    if 'cards' not in session or 'current_index' not in session:
        return redirect(url_for('index'))
    
    # Get the previous card (now at current_index - 1)
    index = session['current_index'] - 1
    cards = session['cards']
    
    if index < 0 or index >= len(cards):
        return redirect(url_for('show_card'))
    
    card = cards[index]
    return render_template('feedback.html', card=card, correct=(correct == 'true'))

@app.route('/next')
def next_card():
    return redirect(url_for('show_card'))

@app.route('/results')
def show_results():
    if 'cards' not in session or 'answers' not in session:
        return redirect(url_for('index'))
    
    # Convert session data back to Card objects
    cards = [Card(**card_data) for card_data in session['cards']]
    
    # Check if authenticated
    is_authenticated = 'credentials' in session
    
    # Update the spreadsheet if authenticated
    updated = False
    if is_authenticated:
        try:
            update_result = update_spreadsheet(cards)
            updated = True
        except Exception as e:
            print(f"Error updating spreadsheet: {e}")
    
    # Get statistics
    answers = session.get('answers', [])
    total = len(answers)
    correct = sum(1 for a in answers if a['correct'])
    
    # Clear session data
    session.pop('cards', None)
    session.pop('current_index', None)
    session.pop('answers', None)
    
    return render_template('results.html', 
                          total=total, 
                          correct=correct, 
                          percentage=round(correct/total*100) if total else 0,
                          updated=updated,
                          is_authenticated=is_authenticated)

@app.route('/test')
def test():
    """Simple test route to verify server is working."""
    return "Server is working correctly! You can go back to the <a href='/'>homepage</a>."

if __name__ == '__main__':
    # Check if the client secrets file exists
    if not pathlib.Path(CLIENT_SECRETS_FILE).exists():
        print(f"WARNING: {CLIENT_SECRETS_FILE} not found. OAuth authentication will not work.")
        print("You'll need to create a project in Google Cloud Console and download the client secret.")
        print("See README.md for instructions.")
    
    # For OAuth callback to work properly, we need to ensure localhost is used
    # and environment variable is set to allow insecure OAuth for development
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    print("NOTICE: OAuth insecure transport enabled for local development")
    print("IMPORTANT: Don't use this in production!")
    
    # Use port 8080 since port 5000 is problematic
    app.run(debug=True, host='localhost', port=8080)
