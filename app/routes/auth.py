"""
Authentication routes for the Language Learning Flashcard App.

Handles Google OAuth authentication flow using centralized AuthManager.
"""

import logging

from flask import Blueprint, redirect, render_template, request, url_for

from app.config import Environment, config
from app.services.auth_manager import auth_manager

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


@auth_bp.route("/clear")
def clear_credentials():
    """Logout user and clear credentials."""
    auth_manager.logout()
    return redirect(url_for("index.home"))
