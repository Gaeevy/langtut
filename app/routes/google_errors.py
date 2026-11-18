"""Render Google connection failures at the website boundary."""

from flask import Flask, jsonify, render_template, request, url_for

from app.services.google_credentials import (
    GoogleConnectionRequiredError,
    GoogleCredentialsUnavailableError,
)


def register_google_error_handlers(app: Flask) -> None:
    @app.errorhandler(GoogleConnectionRequiredError)
    def connection_required(error):
        if request.is_json or request.path.startswith("/api/") or request.endpoint == "test.test":
            return jsonify(
                success=False,
                error="Google Sheets connection required",
                code="google_sheets_connection_required",
                connect_url=url_for("index.home"),
            ), 403
        return render_template("sheets_connection.html", message=str(error)), 403

    @app.errorhandler(GoogleCredentialsUnavailableError)
    def temporarily_unavailable(error):
        message = "Google Sheets is temporarily unavailable. Try again."
        if request.is_json or request.path.startswith("/api/") or request.endpoint == "test.test":
            return jsonify(success=False, error=message, code="google_sheets_unavailable"), 503
        return render_template("error.html", message=message), 503
