"""
Authentication routes for the Language Learning Flashcard App.

Handles Google OAuth authentication flow using centralized AuthManager.
"""

import logging

from flask import Blueprint, redirect, render_template, request, url_for
from google.auth.exceptions import TransportError
from requests.exceptions import RequestException
from sqlalchemy.exc import SQLAlchemyError

from app import csrf
from app.config import Environment, config
from app.services.auth_manager import auth_manager
from app.services.google_credentials import (
    GoogleConnectionRequiredError,
    GoogleCredentialsUnavailableError,
)
from app.services.google_oauth import GoogleAuthorizationError

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


def _redirect_uri() -> str:
    use_https = config.environment == Environment.PRODUCTION or "ngrok" in request.host
    scheme = "https" if use_https else "http"
    return f"{scheme}://{request.host}{url_for('auth.oauth2callback')}"


@auth_bp.route("/auth")
def auth():
    """Initiate OAuth flow."""
    try:
        authorization_url = auth_manager.initiate_login(_redirect_uri())
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
        auth_manager.handle_callback(authorization_response)

        return redirect(url_for("index.home"))

    except (GoogleConnectionRequiredError, GoogleCredentialsUnavailableError):
        raise
    except GoogleAuthorizationError as error:
        return render_template("error.html", message=f"Google authorization failed. {error}"), 400
    except (TransportError, RequestException):
        return render_template(
            "error.html", message="Google is temporarily unavailable. Try again."
        ), 503
    except Exception as e:
        logger.warning("Google sign-in callback failed (%s)", type(e).__name__)
        return render_template(
            "error.html",
            message="Google authorization failed. Check your account and permissions, then try again.",
        ), 400


@auth_bp.post("/connect-google-sheets")
@auth_manager.require_auth
def connect_google_sheets():
    """Request Sheets consent for the signed-in Google account."""
    csrf.protect()
    try:
        return redirect(auth_manager.initiate_connection(_redirect_uri()))
    except Exception as error:
        logger.warning("Could not start Sheets connection (%s)", type(error).__name__)
        return render_template(
            "error.html", message="Could not connect Google Sheets. Try again."
        ), 503


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
