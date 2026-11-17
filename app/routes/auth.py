"""
Authentication routes for the Language Learning Flashcard App.

Handles Google OAuth authentication flow using centralized AuthManager.
"""

import logging

from flask import Blueprint, redirect, render_template, request, url_for
from sqlalchemy.exc import SQLAlchemyError

from app import csrf
from app.config import Environment, config
from app.services.auth_manager import auth_manager
from app.services.google_credentials import GoogleCredentialsUnavailableError

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/auth")
def auth():
    """Initiate OAuth flow."""
    try:
        use_https = config.environment == Environment.PRODUCTION or "ngrok" in request.host
        scheme = "https" if use_https else "http"
        redirect_uri = f"{scheme}://{request.host}{url_for('auth.oauth2callback')}"
        authorization_url = auth_manager.initiate_login(redirect_uri)
        return redirect(authorization_url)
    except Exception as e:
        logger.error("Could not start Google sign-in (%s)", type(e).__name__)
        return render_template("error.html", message="Could not start Google sign-in.")


@auth_bp.route("/oauth2callback")
def oauth2callback():
    """OAuth callback handler."""
    try:
        # Fix for Railway: ensure HTTPS in authorization response URL
        authorization_response = request.url
        if config.environment == Environment.PRODUCTION and authorization_response.startswith(
            "http://"
        ):
            authorization_response = authorization_response.replace("http://", "https://", 1)

        # Handle callback and create/login user
        user = auth_manager.handle_callback(authorization_response)

        logger.info("User %s signed in with Google", user.id)
        return redirect(url_for("index.home"))

    except Exception as e:
        logger.warning("Google sign-in callback failed (%s)", type(e).__name__)
        return render_template("error.html", message="OAuth callback error. Start sign-in again.")


@auth_bp.post("/clear")
@auth_manager.require_auth
def logout():
    """End the current browser login."""
    csrf.protect()
    auth_manager.logout()
    return redirect(url_for("index.home"))


@auth_bp.post("/logout-everywhere")
@auth_manager.require_auth
def logout_everywhere():
    """Invalidate all browser logins for the current user."""
    csrf.protect()
    try:
        auth_manager.logout(logout_all_devices=True)
    except SQLAlchemyError:
        logger.warning("Could not log out the user on all devices")
        return render_template("error.html", message="Could not log out on all devices."), 503
    return redirect(url_for("index.home"))


@auth_bp.post("/disconnect-google-sheets")
@auth_manager.require_auth
def disconnect_google_sheets():
    """Remove LangTut's Google Sheets connection."""
    csrf.protect()
    try:
        auth_manager.disconnect_google_sheets()
    except GoogleCredentialsUnavailableError:
        logger.warning("Could not disconnect Google Sheets")
        return render_template("error.html", message="Could not disconnect Google Sheets."), 503
    return redirect(url_for("index.home"))
