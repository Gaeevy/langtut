"""
Authentication routes for the Language Learning Flashcard App.

Handles Google OAuth authentication flow.
"""

from flask import Blueprint, redirect, render_template, request, session, url_for
from google_auth_oauthlib.flow import Flow

from src.auth import credentials_to_dict
from src.config import config
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
        # Determine if we're in production or development
        is_production = request.host.endswith('.railway.app') or request.host.endswith(
            '.up.railway.app'
        )

        if is_production:
            # In production, use the Railway domain
            redirect_uri = f'https://{request.host}/oauth2callback'
        else:
            # In development, support localhost, network IP, and ngrok
            host_parts = request.host.split(':')
            host_ip = host_parts[0]
            port = host_parts[1] if len(host_parts) > 1 else '8080'

            if host_ip == 'localhost' or host_ip == '127.0.0.1':
                # Standard localhost development
                redirect_uri = f'http://localhost:{port}/oauth2callback'
            elif 'ngrok' in request.host:
                # Ngrok tunnel for mobile testing
                redirect_uri = f'https://{request.host}/oauth2callback'
            else:
                # Network IP for mobile testing
                redirect_uri = f'http://{request.host}/oauth2callback'

        # Verify the redirect URI is in our registered list
        if REGISTERED_REDIRECT_URIS and redirect_uri not in REGISTERED_REDIRECT_URIS:
            # For development: allow network IP redirects for mobile testing
            is_dev_mobile_testing = (
                not is_production and host_ip != 'localhost' and host_ip != '127.0.0.1'
            )

            if not is_dev_mobile_testing:
                # Fall back to a registered URI that matches our environment
                if is_production:
                    production_uris = [
                        uri for uri in REGISTERED_REDIRECT_URIS if 'railway.app' in uri
                    ]
                    if production_uris:
                        redirect_uri = production_uris[0]
                else:
                    localhost_uris = [uri for uri in REGISTERED_REDIRECT_URIS if 'localhost' in uri]
                    if localhost_uris:
                        redirect_uri = localhost_uris[0]

        # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps
        flow = Flow.from_client_secrets_file(
            config.client_secrets_file_path, scopes=config.scopes, redirect_uri=redirect_uri
        )

        # Generate URL for request to Google's OAuth 2.0 server
        authorization_url, state = flow.authorization_url(
            access_type='offline', include_granted_scopes='true'
        )

        # Store the state and redirect URI for later verification
        sm.set(sk.AUTH_STATE, state)
        sm.set(sk.AUTH_REDIRECT_URI, redirect_uri)

        return redirect(authorization_url)
    except Exception as e:
        return render_template('error.html', message=f'Authentication error: {e!s}')


@auth_bp.route('/oauth2callback')
def oauth2callback():
    """Callback function for the OAuth flow."""
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
            is_production = request.host.endswith('.railway.app') or request.host.endswith(
                '.up.railway.app'
            )

            if is_production:
                redirect_uri = f'https://{request.host}/oauth2callback'
            else:
                # Same logic as auth route: support localhost, network IP, and ngrok
                host_parts = request.host.split(':')
                host_ip = host_parts[0]
                port = host_parts[1] if len(host_parts) > 1 else '8080'

                if host_ip == 'localhost' or host_ip == '127.0.0.1':
                    redirect_uri = f'http://localhost:{port}/oauth2callback'
                elif 'ngrok' in request.host:
                    redirect_uri = f'https://{request.host}/oauth2callback'
                else:
                    redirect_uri = f'http://{request.host}/oauth2callback'

        flow = Flow.from_client_secrets_file(
            config.client_secrets_file_path,
            scopes=config.scopes,
            state=state,
            redirect_uri=redirect_uri,
        )

        # Get the authorization response from the request
        authorization_response = request.url

        # Fix for Railway: ensure HTTPS in authorization response URL
        if authorization_response.startswith('http://') and (
            request.host.endswith('.railway.app') or request.host.endswith('.up.railway.app')
        ):
            authorization_response = authorization_response.replace('http://', 'https://', 1)

        flow.fetch_token(authorization_response=authorization_response)

        # Store credentials in the session
        credentials = flow.credentials
        credentials_dict = credentials_to_dict(credentials)
        sm.set(sk.AUTH_CREDENTIALS, credentials_dict)

        # Login user and create/update user record
        try:
            login_user(session, credentials_dict)
        except Exception as e:
            return render_template('error.html', message=f'Login error: {e!s}')

        # After authentication, redirect to index which will check for existing spreadsheet
        return redirect(url_for('flashcard.index'))
    except Exception as e:
        return render_template('error.html', message=f'OAuth callback error: {e!s}')


@auth_bp.route('/clear')
def clear_credentials():
    """Clear the stored credentials and redirect to login."""
    clear_user_session(session)
    return redirect(url_for('flashcard.index'))
