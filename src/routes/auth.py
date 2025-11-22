"""
Authentication routes for the Language Learning Flashcard App.

Handles Google OAuth authentication flow.
"""

import logging

from flask import Blueprint, redirect, render_template, request, url_for

from src.services.auth import create_oauth_flow, credentials_to_dict, get_redirect_uri
from src.session_manager import SessionKeys as sk
from src.session_manager import SessionManager as sm
from src.user_manager import clear_user_session, login_user

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/auth")
def auth():
    """Initiate OAuth flow."""
    try:
        redirect_uri = get_redirect_uri(request.host)
        flow = create_oauth_flow(redirect_uri)

        authorization_url, state = flow.authorization_url(
            access_type="offline", include_granted_scopes="true"
        )

        sm.set(sk.AUTH_STATE, state)
        sm.set(sk.AUTH_REDIRECT_URI, redirect_uri)

        return redirect(authorization_url)
    except Exception as e:
        logger.error(f"Error initiating OAuth flow: {e}")
        return render_template("error.html", message=f"Authentication error: {e!s}")


@auth_bp.route("/oauth2callback")
def oauth2callback():
    """OAuth callback handler."""
    state = sm.get(sk.AUTH_STATE)
    if not state or state != request.args.get("state"):
        return render_template("error.html", message="Invalid state parameter")

    try:
        redirect_uri = sm.get(sk.AUTH_REDIRECT_URI) or get_redirect_uri(request.host)
        flow = create_oauth_flow(redirect_uri, state)

        authorization_response = request.url
        flow.fetch_token(authorization_response=authorization_response)

        credentials = flow.credentials
        credentials_dict = credentials_to_dict(credentials)
        sm.set(sk.AUTH_CREDENTIALS, credentials_dict)

        login_user(credentials_dict)
        return redirect(url_for("flashcard.index"))
    except Exception as e:
        logger.error(f"Error handling OAuth callback: {e}")
        return render_template("error.html", message=f"OAuth callback error: {e!s}")


@auth_bp.route("/clear")
def clear_credentials():
    """Clear stored credentials and redirect to login."""
    clear_user_session()
    return redirect(url_for("flashcard.index"))
