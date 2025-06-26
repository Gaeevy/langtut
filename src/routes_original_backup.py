from flask import render_template, request, redirect, url_for, session, jsonify, flash, Response
from google_auth_oauthlib.flow import Flow
import random
import pathlib
import json
import os
from datetime import datetime

from src import app
from src.auth import get_credentials, credentials_to_dict
from src.gsheet import (
    read_card_set, update_spreadsheet, read_all_card_sets,
    extract_spreadsheet_id, validate_spreadsheet_access
)
from src.models import Card, NEVER_SHOWN
from src.utils import load_redirect_uris, get_timestamp, format_timestamp, parse_timestamp
from src.config import (
    CLIENT_SECRETS_FILE, SCOPES,
    API_SERVICE_NAME, API_VERSION, MAX_CARDS_PER_SESSION, SPREADSHEET_ID
)
from src.user_manager import (
    login_user, get_current_user_from_session, get_user_spreadsheet_id,
    set_user_spreadsheet, clear_user_session
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

def get_user_spreadsheet_id_legacy():
    """Legacy function - now uses database instead of session"""
    return get_user_spreadsheet_id(session)

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

    # If not authenticated, show login screen
    if not is_authenticated:
        return render_template('login.html')

    # Get the user's active spreadsheet ID
    user_spreadsheet_id = get_user_spreadsheet_id(session)

    # If no spreadsheet set, show setup screen
    if not user_spreadsheet_id:
        return render_template('setup.html', is_authenticated=is_authenticated)

    # Normal app flow with user's spreadsheet
    card_sets = read_all_card_sets(user_spreadsheet_id)

    return render_template('index.html',
                         is_authenticated=is_authenticated,
                         tabs=card_sets,
                         user_spreadsheet_id=user_spreadsheet_id)


@app.route('/start/<tab_name>', methods=['POST'])
def start_learning(tab_name):
    # Get user's active spreadsheet
    user_spreadsheet_id = get_user_spreadsheet_id(session)

    # Read cards from the specified tab
    card_set = read_card_set(worksheet_name=tab_name, spreadsheet_id=user_spreadsheet_id)
    cards = card_set.get_cards_to_review(limit=MAX_CARDS_PER_SESSION, ignore_unshown=False)

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
        # Get the current request URL and determine the correct redirect URI
        current_url = request.url
        print(f"Auth request URL: {current_url}")

        # Determine if we're in production or development
        is_production = request.host.endswith('.railway.app') or request.host.endswith('.up.railway.app')

        if is_production:
            # In production, use the Railway domain
            redirect_uri = f"https://{request.host}/oauth2callback"
        else:
            # In development, use localhost with the appropriate port
            parts = request.host.split(':')
            port = parts[1] if len(parts) > 1 else '8080'
            redirect_uri = f'http://localhost:{port}/oauth2callback'

        # Verify the redirect URI is in our registered list
        if REGISTERED_REDIRECT_URIS and redirect_uri not in REGISTERED_REDIRECT_URIS:
            print(f"Warning: {redirect_uri} not in registered URIs: {REGISTERED_REDIRECT_URIS}")
            # Fall back to a registered URI that matches our environment
            if is_production:
                production_uris = [uri for uri in REGISTERED_REDIRECT_URIS if 'railway.app' in uri]
                if production_uris:
                    redirect_uri = production_uris[0]
            else:
                localhost_uris = [uri for uri in REGISTERED_REDIRECT_URIS if 'localhost' in uri]
                if localhost_uris:
                    redirect_uri = localhost_uris[0]

        print(f"Using redirect URI for auth: {redirect_uri}")
        print(f"Using OAuth scopes: {SCOPES}")

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
            is_production = request.host.endswith('.railway.app') or request.host.endswith('.up.railway.app')

            if is_production:
                redirect_uri = f"https://{request.host}/oauth2callback"
            else:
                parts = request.host.split(':')
                port = parts[1] if len(parts) > 1 else '8080'
                redirect_uri = f'http://localhost:{port}/oauth2callback'

        print(f"Using redirect URI for callback: {redirect_uri}")

        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, scopes=SCOPES,
            state=state,
            redirect_uri=redirect_uri)

        # Get the authorization response from the request
        authorization_response = request.url
        print(f"Authorization response: {authorization_response}")

        # Fix for Railway: ensure HTTPS in authorization response URL
        if authorization_response.startswith('http://') and (request.host.endswith('.railway.app') or request.host.endswith('.up.railway.app')):
            authorization_response = authorization_response.replace('http://', 'https://', 1)
            print(f"Fixed authorization response for Railway: {authorization_response}")

        flow.fetch_token(authorization_response=authorization_response)

        # Store credentials in the session
        credentials = flow.credentials
        credentials_dict = credentials_to_dict(credentials)
        session['credentials'] = credentials_dict

        # Login user and create/update user record
        try:
            user = login_user(session, credentials_dict)
            print(f"User {user.email} logged in successfully")
        except Exception as e:
            print(f"Error during user login: {e}")
            return render_template('error.html', message=f"Login error: {str(e)}")

        # After authentication, redirect to index which will check for existing spreadsheet
        return redirect(url_for('index'))
    except Exception as e:
        print(f"OAuth callback error: {str(e)}")
        return render_template('error.html', message=f"OAuth callback error: {str(e)}")


@app.route('/clear')
def clear_credentials():
    """Clear the stored credentials and redirect to login."""
    clear_user_session(session)
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
            current_card['level'] = current_card['level'].next_level()
    else:
        # For incorrect answers, track the card for review if this is the first attempt
        if not reviewing:
            session['incorrect_cards'].append(index)
        else:
            # If this is a review and still incorrect, decrease the level
            current_card['level'] = current_card['level'].previous_level()

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
        card['level'] = card['level'].next_level()
    elif difficulty == 'difficult':
        # Decrease level if rated difficult (but not below 0)
        card['level'] = card['level'].previous_level()

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
            user_spreadsheet_id = get_user_spreadsheet_id(session)
            update_result = update_spreadsheet(session['active_tab'], card_objects, user_spreadsheet_id)
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
    """Simple test route to verify server and database are working."""
    try:
        # Test database connection
        from src.database import db, User, ensure_tables
        ensure_tables()
        user_count = User.query.count()
        db_status = f"Database connected. Users: {user_count}"
    except Exception as e:
        db_status = f"Database error: {str(e)}"

    return f"""
    <h2>🚀 Language Learning App - Health Check</h2>
    <p>✅ Server is working correctly!</p>
    <p>📊 {db_status}</p>
    <p>🌍 Environment: {'Railway' if os.getenv('RAILWAY_ENVIRONMENT') else 'Local'}</p>
    <p><a href='/'>← Go to homepage</a></p>
    """


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
            user_spreadsheet_id = get_user_spreadsheet_id(session)
            update_result = update_spreadsheet(session['active_tab'], seen_cards, user_spreadsheet_id)
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

    # Calculate review counts
    review_count = 0
    first_attempt_count = total

    return render_template('results.html',
                           total=total,
                           correct=correct,
                           percentage=round(correct / total * 100) if total else 0,
                           updated=updated,
                           is_authenticated=is_authenticated,
                           tab_name=active_tab,
                           ended_early=True,
                           cards_remaining=remaining,
                           review_count=review_count,
                           first_attempt_count=first_attempt_count)


@app.route('/settings')
def settings():
    """Settings page for managing user's spreadsheet"""
    if 'credentials' not in session:
        flash('Please log in with Google to manage your spreadsheet settings.', 'warning')
        return redirect(url_for('index'))

    user_spreadsheet_id = get_user_spreadsheet_id(session)

    return render_template('settings.html',
                         user_spreadsheet_id=user_spreadsheet_id)


@app.route('/validate-spreadsheet', methods=['POST'])
def validate_spreadsheet():
    """Validate a spreadsheet URL/ID via AJAX"""
    if 'credentials' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'})

    spreadsheet_url = request.json.get('spreadsheet_url', '').strip()
    if not spreadsheet_url:
        return jsonify({'success': False, 'error': 'Please provide a spreadsheet URL or ID'})

    try:
        # Extract spreadsheet ID from URL
        spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)

        # Validate access and format
        is_valid, error_message, worksheet_names = validate_spreadsheet_access(spreadsheet_id)

        if is_valid:
            return jsonify({
                'success': True,
                'spreadsheet_id': spreadsheet_id,
                'worksheets': worksheet_names,
                'message': 'Spreadsheet is valid and accessible!'
            })
        else:
            return jsonify({'success': False, 'error': error_message})

    except Exception as e:
        return jsonify({'success': False, 'error': f'Error validating spreadsheet: {str(e)}'})


@app.route('/set-spreadsheet', methods=['POST'])
def set_spreadsheet():
    """Set the user's active spreadsheet"""
    if 'credentials' not in session:
        flash('Please log in with Google to set your spreadsheet.', 'error')
        return redirect(url_for('settings'))

    spreadsheet_url = request.form.get('spreadsheet_url', '').strip()
    if not spreadsheet_url:
        flash('Please provide a spreadsheet URL or ID.', 'error')
        return redirect(url_for('settings'))

    try:
        # Extract and validate spreadsheet ID
        spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
        is_valid, error_message, worksheet_names = validate_spreadsheet_access(spreadsheet_id)

        if is_valid:
            # Store in database
            try:
                set_user_spreadsheet(session, spreadsheet_id, spreadsheet_url)
                flash(f'Successfully linked your spreadsheet! Found {len(worksheet_names)} worksheet(s): {", ".join(worksheet_names)}', 'success')
            except Exception as e:
                flash(f'Error saving spreadsheet: {str(e)}', 'error')
        else:
            flash(f'Error: {error_message}', 'error')

    except Exception as e:
        flash(f'Error setting spreadsheet: {str(e)}', 'error')

    return redirect(url_for('settings'))


@app.route('/reset-spreadsheet', methods=['POST'])
def reset_spreadsheet():
    """Reset spreadsheet - remove active spreadsheet from database"""
    user = get_current_user_from_session(session)
    if user:
        # Deactivate all spreadsheets for this user
        from src.database import UserSpreadsheet, db
        UserSpreadsheet.query.filter_by(user_id=user.id, is_active=True).update({'is_active': False})
        db.session.commit()

    flash('Spreadsheet reset. Please set up a new one.', 'info')
    return redirect(url_for('index'))  # Will show setup screen


@app.route('/admin/db-info')
def db_info():
    """Database information endpoint for debugging"""
    try:
        from src.database import db, User, UserSpreadsheet, ensure_tables
        ensure_tables()

        # Get database stats
        user_count = User.query.count()
        spreadsheet_count = UserSpreadsheet.query.count()
        active_spreadsheets = UserSpreadsheet.query.filter_by(is_active=True).count()

        # Get recent users
        recent_users = User.query.order_by(User.last_login.desc()).limit(5).all()

        # Get recent spreadsheets
        recent_spreadsheets = UserSpreadsheet.query.order_by(UserSpreadsheet.last_used.desc()).limit(5).all()

        info = {
            'database_stats': {
                'total_users': user_count,
                'total_spreadsheets': spreadsheet_count,
                'active_spreadsheets': active_spreadsheets
            },
            'recent_users': [user.to_dict() for user in recent_users],
            'recent_spreadsheets': [sheet.to_dict() for sheet in recent_spreadsheets],
            'environment': 'Railway' if os.getenv('RAILWAY_ENVIRONMENT') else 'Local',
            'database_path': app.config.get('SQLALCHEMY_DATABASE_URI', 'Not configured')
        }

        return jsonify(info)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/users')
def list_users():
    """List all users in the database"""
    try:
        from src.database import User, ensure_tables
        ensure_tables()
        users = User.query.order_by(User.last_login.desc()).all()
        return jsonify([user.to_dict() for user in users])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/spreadsheets')
def list_spreadsheets():
    """List all spreadsheets in the database"""
    try:
        from src.database import UserSpreadsheet
        spreadsheets = UserSpreadsheet.query.order_by(UserSpreadsheet.last_used.desc()).all()
        return jsonify([sheet.to_dict() for sheet in spreadsheets])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/user/<int:user_id>')
def get_user_details(user_id):
    """Get detailed information about a specific user"""
    try:
        from src.database import User
        user = User.query.get_or_404(user_id)
        user_data = user.to_dict()
        user_data['spreadsheets'] = [sheet.to_dict() for sheet in user.spreadsheets]
        return jsonify(user_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/export-db')
def export_database():
    """Export database as SQL dump"""
    try:
        import sqlite3
        import tempfile
        from flask import Response

        # Get database path from config
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if db_uri.startswith('sqlite:///'):
            db_path = db_uri.replace('sqlite:///', '')
        else:
            return jsonify({'error': 'Not a SQLite database'}), 400

        # Create SQL dump
        conn = sqlite3.connect(db_path)
        dump_lines = []
        for line in conn.iterdump():
            dump_lines.append(line)
        conn.close()

        dump_content = '\n'.join(dump_lines)

        return Response(
            dump_content,
            mimetype='application/sql',
            headers={'Content-Disposition': 'attachment; filename=database_dump.sql'}
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/query', methods=['POST'])
def execute_query():
    """Execute a custom SQL query (READ-ONLY for safety)"""
    try:
        import sqlite3
        from flask import request

        query = request.json.get('query', '').strip()
        if not query:
            return jsonify({'error': 'No query provided'}), 400

        # Safety check - only allow SELECT queries
        if not query.upper().startswith('SELECT'):
            return jsonify({'error': 'Only SELECT queries are allowed'}), 400

        # Get database path
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if db_uri.startswith('sqlite:///'):
            db_path = db_uri.replace('sqlite:///', '')
        else:
            return jsonify({'error': 'Not a SQLite database'}), 400

        # Execute query
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        cursor = conn.cursor()
        cursor.execute(query)

        # Fetch results
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]

        # Convert to list of dictionaries
        results = []
        for row in rows:
            results.append(dict(zip(columns, row)))

        conn.close()

        return jsonify({
            'query': query,
            'columns': columns,
            'rows': results,
            'count': len(results)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/volume-check')
def volume_check():
    """Check Railway volume mount status and persistence"""
    try:
        import os
        import time
        from datetime import datetime

        # Get database path
        database_path = os.getenv('DATABASE_PATH', '/app/data/app.db')
        database_dir = os.path.dirname(database_path)

        info = {
            'database_path': database_path,
            'database_dir': database_dir,
            'database_dir_exists': os.path.exists(database_dir),
            'database_file_exists': os.path.exists(database_path),
            'environment': 'Railway' if os.getenv('RAILWAY_ENVIRONMENT') else 'Local'
        }

        # Check directory permissions
        if os.path.exists(database_dir):
            info['dir_writable'] = os.access(database_dir, os.W_OK)
            info['dir_readable'] = os.access(database_dir, os.R_OK)

            # List files in directory
            try:
                files = os.listdir(database_dir)
                info['files_in_dir'] = files
            except Exception as e:
                info['files_in_dir'] = f"Error: {e}"

        # Check database file details
        if os.path.exists(database_path):
            stat = os.stat(database_path)
            info['db_file_size'] = stat.st_size
            info['db_file_modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
            info['db_file_created'] = datetime.fromtimestamp(stat.st_ctime).isoformat()

        # Create a test persistence file
        test_file = os.path.join(database_dir, 'persistence_test.txt')
        current_time = datetime.now().isoformat()

        try:
            # Try to read existing test file
            if os.path.exists(test_file):
                with open(test_file, 'r') as f:
                    info['previous_deployment_time'] = f.read().strip()
                info['persistence_test'] = 'PASS - File persisted from previous deployment'
            else:
                info['persistence_test'] = 'NEW - No previous test file found'

            # Write current deployment time
            with open(test_file, 'w') as f:
                f.write(current_time)
            info['current_deployment_time'] = current_time

        except Exception as e:
            info['persistence_test'] = f'FAIL - Cannot write test file: {e}'

        # Check if volume is actually mounted (Railway specific)
        if os.getenv('RAILWAY_ENVIRONMENT'):
            # Check if /app/data is a mount point
            try:
                # This will show different device IDs if it's a mount point
                root_stat = os.stat('/app')
                data_stat = os.stat('/app/data') if os.path.exists('/app/data') else None

                if data_stat:
                    info['volume_mounted'] = root_stat.st_dev != data_stat.st_dev
                    info['root_device'] = root_stat.st_dev
                    info['data_device'] = data_stat.st_dev
                else:
                    info['volume_mounted'] = False
                    info['mount_error'] = '/app/data does not exist'

            except Exception as e:
                info['volume_check_error'] = str(e)

        return jsonify(info)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Text-to-Speech Routes
@app.route('/api/tts/status')
def tts_status():
    """Check TTS service availability"""
    try:
        from src.tts_service import is_tts_available, get_portuguese_voices, tts_service

        status = {
            'available': is_tts_available(),
            'language_code': 'pt-PT',
            'voices': get_portuguese_voices() if is_tts_available() else [],
            'credential_info': tts_service.get_credential_info()
        }

        return jsonify(status)

    except Exception as e:
        return jsonify({'error': str(e), 'available': False}), 500


@app.route('/api/tts/speak', methods=['POST'])
def generate_speech():
    """Generate speech from text"""
    try:
        from src.tts_service import generate_portuguese_speech, is_tts_available
        from src.gsheet import read_card_set

        if not is_tts_available():
            return jsonify({'error': 'TTS service is not available'}), 503

        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'error': 'Text is required'}), 400

        text = data.get('text', '').strip()
        voice_name = data.get('voice_name')  # Optional voice override

        if not text:
            return jsonify({'error': 'Text cannot be empty'}), 400

        # Get caching context from session (if available)
        spreadsheet_id = None
        sheet_gid = None

        try:
            # Get current user's spreadsheet
            user_spreadsheet_id = get_user_spreadsheet_id(session)
            if user_spreadsheet_id and 'active_tab' in session:
                spreadsheet_id = user_spreadsheet_id
                # Get the current tab's gid
                active_tab = session['active_tab']
                card_set = read_card_set(active_tab, user_spreadsheet_id)
                if card_set:
                    sheet_gid = card_set.gid
        except Exception as e:
            print(f"⚠️ Could not get caching context: {e}")
            # Continue without caching context

        # Generate speech (with caching if context available)
        audio_base64 = generate_portuguese_speech(text, voice_name, spreadsheet_id, sheet_gid)

        if audio_base64:
            return jsonify({
                'success': True,
                'audio_base64': audio_base64,
                'text': text,
                'voice_name': voice_name,
                'format': 'mp3'
            })
        else:
            return jsonify({'error': 'Failed to generate speech'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tts/speak-card', methods=['POST'])
def speak_card_content():
    """Generate speech for card content (word and example)"""
    try:
        from src.tts_service import generate_portuguese_speech, is_tts_available
        from src.gsheet import read_card_set

        if not is_tts_available():
            return jsonify({'error': 'TTS service is not available'}), 503

        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request data is required'}), 400

        word = data.get('word', '').strip()
        example = data.get('example', '').strip()
        voice_name = data.get('voice_name')  # Optional voice override

        # Get caching context from session (if available)
        spreadsheet_id = None
        sheet_gid = None

        try:
            # Get current user's spreadsheet
            user_spreadsheet_id = get_user_spreadsheet_id(session)
            if user_spreadsheet_id and 'active_tab' in session:
                spreadsheet_id = user_spreadsheet_id
                # Get the current tab's gid
                active_tab = session['active_tab']
                card_set = read_card_set(active_tab, user_spreadsheet_id)
                if card_set:
                    sheet_gid = card_set.gid
        except Exception as e:
            print(f"⚠️ Could not get caching context: {e}")
            # Continue without caching context

        result = {
            'success': True,
            'audio': {}
        }

        # Generate speech for word
        if word:
            word_audio = generate_portuguese_speech(word, voice_name, spreadsheet_id, sheet_gid)
            if word_audio:
                result['audio']['word'] = {
                    'text': word,
                    'audio_base64': word_audio,
                    'format': 'mp3'
                }

        # Generate speech for example
        if example:
            example_audio = generate_portuguese_speech(example, voice_name, spreadsheet_id, sheet_gid)
            if example_audio:
                result['audio']['example'] = {
                    'text': example,
                    'audio_base64': example_audio,
                    'format': 'mp3'
                }

        # Check if we generated any audio
        if not result['audio']:
            return jsonify({'error': 'No valid text provided for speech generation'}), 400

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/test-tts')
def test_tts():
    """Test page for TTS functionality"""
    return render_template('test_tts.html')
