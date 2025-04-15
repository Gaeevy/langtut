from flask import render_template, request, redirect, url_for, session, jsonify
from google_auth_oauthlib.flow import Flow
import random
import pathlib
import json
from datetime import datetime

from src import app
from src.auth import get_credentials, credentials_to_dict
from src.gsheet import read_spreadsheet, update_spreadsheet
from src.models import Card, NEVER_SHOWN
from src.utils import load_redirect_uris, get_timestamp, format_timestamp, parse_timestamp
from src.config import (
    MAX_CARDS_PER_SESSION, CLIENT_SECRETS_FILE, SCOPES, 
    API_SERVICE_NAME, API_VERSION
)

# Load registered redirect URIs from client_secret.json
REGISTERED_REDIRECT_URIS = load_redirect_uris()

# Custom JSON encoder to handle datetime objects
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return format_timestamp(obj)
        return super().default(obj)

# Set custom JSON encoder for Flask
app.json_encoder = CustomJSONEncoder

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

    # Get tabs
    tabs = read_spreadsheet()

    return render_template('index.html', is_authenticated=is_authenticated, tabs=tabs)


@app.route('/start/<tab_name>', methods=['POST'])
def start_learning(tab_name):
    # Read cards from the specified tab
    cards = read_spreadsheet(sheet_name=tab_name)
    if not cards:
        return render_template('error.html', message=f'No cards found in the tab {tab_name}')

    # Limit cards to MAX_CARDS_PER_SESSION
    if len(cards) > MAX_CARDS_PER_SESSION:
        # Shuffle and select random cards
        random.shuffle(cards)
        cards = cards[:MAX_CARDS_PER_SESSION]

    # Store cards in session (converted to dict for JSON serialization)
    # We need to format datetime objects to strings for JSON serialization
    cards_data = []
    for card in cards:
        card_dict = card.model_dump()
        card_dict['last_shown'] = format_timestamp(card.last_shown)
        cards_data.append(card_dict)

    session['cards'] = cards_data
    session['current_index'] = 0
    session['answers'] = []
    session['incorrect_cards'] = []  # Track indices of incorrectly answered cards
    session['reviewing_incorrect'] = False  # Flag to indicate if we're reviewing incorrect cards
    session['active_tab'] = tab_name
    session['original_card_count'] = len(cards)  # Store total card count for reference

    # Redirect to the first card
    return redirect(url_for('show_card'))


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


@app.route('/card')
def show_card():
    if 'cards' not in session or 'current_index' not in session:
        return redirect(url_for('index'))

    cards = session['cards']
    index = session['current_index']
    reviewing = session.get('reviewing_incorrect', False)

    # Check if we've gone through all the initial cards
    if index >= len(cards) and not reviewing:
        # If we have incorrect cards, start reviewing them
        if session.get('incorrect_cards', []):
            session['reviewing_incorrect'] = True
            session['current_index'] = 0
            return redirect(url_for('show_card'))
        else:
            # All cards correct, go to results
            return redirect(url_for('show_results'))

    # If we're reviewing and reached the end of incorrect cards, go to results
    if reviewing and index >= len(session['incorrect_cards']):
        return redirect(url_for('show_results'))

    # Get the current card (either from original list or from incorrect cards)
    if reviewing:
        # Get the incorrect card index from the stored list
        incorrect_idx = session['incorrect_cards'][index]
        current_card = cards[incorrect_idx]
        # Add a flag to indicate this is a review card
        current_card['is_review'] = True
    else:
        current_card = cards[index]
        current_card['is_review'] = False

    return render_template('card.html',
                           card=current_card,
                           index=index,
                           total=len(session['incorrect_cards']) if reviewing else len(cards),
                           reviewing=reviewing)


@app.route('/answer', methods=['POST'])
def process_answer():
    if 'cards' not in session or 'current_index' not in session:
        return redirect(url_for('index'))

    # Get user's answer
    user_answer = request.form.get('answer', '').strip().lower()

    # Check if we're in review mode
    reviewing = session.get('reviewing_incorrect', False)

    # Get current card
    cards = session['cards']
    index = session['current_index']

    if reviewing:
        # Get the original index of the card being reviewed
        original_index = session['incorrect_cards'][index]
        current_card = cards[original_index]
    else:
        current_card = cards[index]

    # Check if answer is correct (simple exact match for MVP)
    correct = user_answer == current_card['word'].lower() or \
              user_answer == current_card['translation'].lower() or \
              user_answer == current_card['equivalent'].lower()

    # Update card stats
    current_card['cnt_shown'] += 1

    if correct:
        current_card['cnt_corr_answers'] += 1
        # Only increase level on first attempt correct answers
        if not reviewing:
            current_card['level'] += 1  # Increase level for correct answer
    else:
        # For incorrect answers, track the card for review if this is the first attempt
        if not reviewing:
            session['incorrect_cards'].append(index)
        else:
            # If this is a review and still incorrect, decrease the level
            current_card['level'] = max(0, current_card['level'] - 1)

    current_card['last_shown'] = format_timestamp(get_timestamp())

    # Store updated card back to session
    if reviewing:
        cards[original_index] = current_card
    else:
        cards[index] = current_card

    session['cards'] = cards

    # Record the answer
    session['answers'] = session.get('answers', []) + [{
        'card_id': current_card['id'],
        'correct': correct,
        'user_answer': user_answer,
        'is_review': reviewing
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
    reviewing = session.get('reviewing_incorrect', False)

    if reviewing:
        if index < 0 or index >= len(session['incorrect_cards']):
            return redirect(url_for('show_card'))

        # Get the original index of the card
        original_index = session['incorrect_cards'][index]
        card = cards[original_index]
    else:
        if index < 0 or index >= len(cards):
            return redirect(url_for('show_card'))

        card = cards[index]

    return render_template('feedback.html',
                           card=card,
                           correct=(correct == 'true'),
                           card_index=original_index if reviewing else index,
                           reviewing=reviewing)


@app.route('/rate-difficulty/<int:card_index>/<difficulty>')
def rate_difficulty(card_index, difficulty):
    """Rate a card as easy or difficult after answering correctly"""
    if 'cards' not in session:
        return redirect(url_for('index'))

    cards = session['cards']

    if card_index < 0 or card_index >= len(cards):
        return redirect(url_for('show_card'))

    # Update the card's level based on difficulty rating
    card = cards[card_index]

    if difficulty == 'easy':
        # Increase level if rated easy
        card['level'] += 1
    elif difficulty == 'difficult':
        # Decrease level if rated difficult (but not below 0)
        card['level'] = max(0, card['level'] - 1)

    # Update the last_shown timestamp
    card['last_shown'] = format_timestamp(get_timestamp())

    # Save the updated card back to session
    cards[card_index] = card
    session['cards'] = cards

    # Continue to the next card
    return redirect(url_for('next_card'))


@app.route('/next')
def next_card():
    return redirect(url_for('show_card'))


@app.route('/results')
def show_results():
    if 'cards' not in session or 'answers' not in session or 'active_tab' not in session:
        return redirect(url_for('index'))

    # Convert session data back to Card objects
    cards_data = session['cards']
    reviewing = session.get('reviewing_incorrect', False)

    # If we're in review mode, make sure we get all the cards (original and reviewed)
    if reviewing:
        # Only include cards that have been seen in either mode
        seen_card_indices = set()

        # Add all cards from the first round
        for i in range(len(cards_data)):
            seen_card_indices.add(i)

        # Convert to Card objects - parse the datetime from string
        card_objects = []
        for i in seen_card_indices:
            card_data = cards_data[i].copy()
            card_data['last_shown'] = parse_timestamp(card_data['last_shown'])
            card_objects.append(Card(**card_data))
    else:
        # Not in review mode, convert all cards
        card_objects = []
        for card_data in cards_data:
            card_copy = card_data.copy()
            card_copy['last_shown'] = parse_timestamp(card_copy['last_shown'])
            card_objects.append(Card(**card_copy))

    # Check if authenticated
    is_authenticated = 'credentials' in session

    # Update the spreadsheet if authenticated
    updated = False
    if is_authenticated:
        try:
            update_result = update_spreadsheet(session['active_tab'], card_objects)
            updated = True
        except Exception as e:
            print(f"Error updating spreadsheet: {e}")

    # Get statistics
    answers = session.get('answers', [])
    total = len(answers)
    correct = sum(1 for a in answers if a['correct'])

    # Count how many cards were reviewed
    first_attempt_answers = [a for a in answers if not a.get('is_review', False)]
    review_answers = [a for a in answers if a.get('is_review', False)]

    # Get active tab name for display
    active_tab = session.get('active_tab', '')

    # Clear session data
    session.pop('cards', None)
    session.pop('current_index', None)
    session.pop('answers', None)
    session.pop('active_tab', None)
    session.pop('original_card_count', None)
    session.pop('incorrect_cards', None)
    session.pop('reviewing_incorrect', None)

    return render_template('results.html',
                           total=total,
                           correct=correct,
                           percentage=round(correct / total * 100) if total else 0,
                           updated=updated,
                           is_authenticated=is_authenticated,
                           tab_name=active_tab,
                           ended_early=False,
                           cards_remaining=0,
                           first_attempt_count=len(first_attempt_answers),
                           review_count=len(review_answers))


@app.route('/test')
def test():
    """Simple test route to verify server is working."""
    return "Server is working correctly! You can go back to the <a href='/'>homepage</a>."


@app.route('/end-session')
def end_session_early():
    """End the learning session early but save progress"""
    if 'cards' not in session or 'active_tab' not in session:
        return redirect(url_for('index'))

    # Get current progress
    cards_data = session['cards']
    current_index = session.get('current_index', 0)
    reviewing = session.get('reviewing_incorrect', False)

    # Convert session data back to Card objects
    if reviewing:
        # Only include cards that have been seen in either mode
        seen_card_indices = set()

        # Add cards seen in the first round
        for i in range(min(current_index, len(cards_data))):
            seen_card_indices.add(i)

        # Add cards seen in review mode
        for i in range(min(current_index, len(session.get('incorrect_cards', [])))):
            original_idx = session['incorrect_cards'][i]
            seen_card_indices.add(original_idx)

        seen_cards = []
        for i in seen_card_indices:
            card_data = cards_data[i].copy()
            card_data['last_shown'] = parse_timestamp(card_data['last_shown'])
            seen_cards.append(Card(**card_data))
    else:
        # Not in review mode, just get the cards we've seen
        seen_cards = []
        for card_data in cards_data[:current_index]:
            card_copy = card_data.copy()
            card_copy['last_shown'] = parse_timestamp(card_copy['last_shown'])
            seen_cards.append(Card(**card_copy))

    # Check if authenticated
    is_authenticated = 'credentials' in session

    # Update the spreadsheet if authenticated
    updated = False
    if is_authenticated and seen_cards:
        try:
            update_result = update_spreadsheet(session['active_tab'], seen_cards)
            updated = True
        except Exception as e:
            print(f"Error updating spreadsheet: {e}")

    # Get statistics for cards seen so far
    answers = session.get('answers', [])
    total = len(answers)
    correct = sum(1 for a in answers if a['correct'])

    # Get active tab name for display
    active_tab = session.get('active_tab', '')

    # Calculate remaining cards
    if reviewing:
        remaining = len(session.get('incorrect_cards', [])) - current_index
    else:
        remaining = len(cards_data) - current_index

    # Clear session data
    session.pop('cards', None)
    session.pop('current_index', None)
    session.pop('answers', None)
    session.pop('active_tab', None)
    session.pop('original_card_count', None)
    session.pop('incorrect_cards', None)
    session.pop('reviewing_incorrect', None)

    return render_template('results.html',
                           total=total,
                           correct=correct,
                           percentage=round(correct / total * 100) if total else 0,
                           updated=updated,
                           is_authenticated=is_authenticated,
                           tab_name=active_tab,
                           ended_early=True,
                           cards_remaining=remaining)