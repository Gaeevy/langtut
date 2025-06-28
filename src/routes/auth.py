"""
Authentication routes for the Language Learning Flashcard App.

Handles Google OAuth authentication flow.
"""

from flask import Blueprint, redirect, render_template, request, session, url_for
from google_auth_oauthlib.flow import Flow

from src.auth import credentials_to_dict
from src.config import CLIENT_SECRETS_FILE, SCOPES
from src.session_manager import SessionKeys as sk
from src.session_manager import SessionManager as sm
from src.user_manager import clear_user_session, login_user
from src.utils import load_redirect_uris

# Create blueprint
auth_bp = Blueprint('auth', __name__)

# Load registered redirect URIs from client_secret.json
REGISTERED_REDIRECT_URIS = load_redirect_uris()


@auth_bp.route('/auth')
def auth():
    """Initiate the OAuth flow to authorize the application."""
    try:
        # Get the current request URL and determine the correct redirect URI
        current_url = request.url
        print(f'Auth request URL: {current_url}')

        # Determine if we're in production or development
        is_production = request.host.endswith('.railway.app') or request.host.endswith(
            '.up.railway.app'
        )

        if is_production:
            # In production, use the Railway domain
            redirect_uri = f'https://{request.host}/oauth2callback'
        else:
            # In development, use localhost with the appropriate port
            parts = request.host.split(':')
            port = parts[1] if len(parts) > 1 else '8080'
            redirect_uri = f'http://localhost:{port}/oauth2callback'

        # Verify the redirect URI is in our registered list
        if REGISTERED_REDIRECT_URIS and redirect_uri not in REGISTERED_REDIRECT_URIS:
            print(f'Warning: {redirect_uri} not in registered URIs: {REGISTERED_REDIRECT_URIS}')
            # Fall back to a registered URI that matches our environment
            if is_production:
                production_uris = [uri for uri in REGISTERED_REDIRECT_URIS if 'railway.app' in uri]
                if production_uris:
                    redirect_uri = production_uris[0]
            else:
                localhost_uris = [uri for uri in REGISTERED_REDIRECT_URIS if 'localhost' in uri]
                if localhost_uris:
                    redirect_uri = localhost_uris[0]

        print(f'Using redirect URI for auth: {redirect_uri}')
        print(f'Using OAuth scopes: {SCOPES}')

        # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=redirect_uri
        )

        # Generate URL for request to Google's OAuth 2.0 server
        authorization_url, state = flow.authorization_url(
            access_type='offline', include_granted_scopes='true'
        )

        # Store the state and redirect URI for later verification
        sm.set(sk.AUTH_STATE, state)
        sm.set(sk.AUTH_REDIRECT_URI, redirect_uri)

        print(f'Authorization URL: {authorization_url}')
        return redirect(authorization_url)
    except Exception as e:
        print(f'Authentication error: {e!s}')
        return render_template('error.html', message=f'Authentication error: {e!s}')


@auth_bp.route('/oauth2callback')
def oauth2callback():
    """Callback function for the OAuth flow."""
    # Print detailed debug information
    print('\n--- OAuth Callback Debug Info ---')
    print(f'Request URL: {request.url}')
    print(f'Request Args: {request.args}')
    print(f'Session Data: {session}')
    print('--------------------------------\n')

    # Ensure that the request is not a forgery and that the user sending
    # this connect request is the expected user
    state = sm.get(sk.AUTH_STATE)

    if not state or state != request.args.get('state'):
        return render_template('error.html', message='Invalid state parameter')

    # Use the authorization server's response to fetch the OAuth 2.0 tokens
    try:
        # Use the same redirect URI that was used for the initial auth request
        redirect_uri = sm.get(sk.AUTH_REDIRECT_URI)
        if not redirect_uri:
            # Fallback if we don't have it in the session
            print('Warning: No redirect_uri in session, constructing one...')
            is_production = request.host.endswith('.railway.app') or request.host.endswith(
                '.up.railway.app'
            )

            if is_production:
                redirect_uri = f'https://{request.host}/oauth2callback'
            else:
                parts = request.host.split(':')
                port = parts[1] if len(parts) > 1 else '8080'
                redirect_uri = f'http://localhost:{port}/oauth2callback'

        print(f'Using redirect URI for callback: {redirect_uri}')

        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, scopes=SCOPES, state=state, redirect_uri=redirect_uri
        )

        # Get the authorization response from the request
        authorization_response = request.url
        print(f'Authorization response: {authorization_response}')

        # Fix for Railway: ensure HTTPS in authorization response URL
        if authorization_response.startswith('http://') and (
            request.host.endswith('.railway.app') or request.host.endswith('.up.railway.app')
        ):
            authorization_response = authorization_response.replace('http://', 'https://', 1)
            print(f'Fixed authorization response for Railway: {authorization_response}')

        flow.fetch_token(authorization_response=authorization_response)

        # Store credentials in the session
        credentials = flow.credentials
        credentials_dict = credentials_to_dict(credentials)
        sm.set(sk.AUTH_CREDENTIALS, credentials_dict)

        # Login user and create/update user record
        try:
            user = login_user(session, credentials_dict)
            print(f'User {user.email} logged in successfully')
        except Exception as e:
            print(f'Error during user login: {e}')
            return render_template('error.html', message=f'Login error: {e!s}')

        # After authentication, redirect to index which will check for existing spreadsheet
        return redirect(url_for('flashcard.index'))
    except Exception as e:
        print(f'OAuth callback error: {e!s}')
        return render_template('error.html', message=f'OAuth callback error: {e!s}')


@auth_bp.route('/clear')
def clear_credentials():
    """Clear the stored credentials and redirect to login."""
    clear_user_session(session)
    return redirect(url_for('flashcard.index'))
