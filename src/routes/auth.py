"""
Authentication routes for the Language Learning Flashcard App.

Handles Google OAuth authentication flow using centralized AuthManager.
"""

import logging

from flask import Blueprint, redirect, render_template, request, url_for

from src.config import Environment, config
from src.services.auth_manager import auth_manager

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/auth")
def auth():
    """Initiate OAuth flow."""
    try:
        authorization_url = auth_manager.initiate_login(request.host)
        return redirect(authorization_url)
    except Exception as e:
        logger.error(f"Error initiating OAuth flow: {e}")
        return render_template("error.html", message=f"Authentication error: {e!s}")


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
        user = auth_manager.handle_callback(authorization_response, request.host)

        logger.info(f"User {user.email} authenticated successfully")
        return redirect(url_for("index.home"))

    except Exception as e:
        logger.error(f"Error handling OAuth callback: {e}")
        return render_template("error.html", message=f"OAuth callback error: {e!s}")


@auth_bp.route("/clear")
def clear_credentials():
    """Logout user and clear credentials."""
    auth_manager.logout()
    return redirect(url_for("index.home"))
