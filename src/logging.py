"""
Logging configuration for Flask application.

Provides basic logging setup and request/response logging with timing and user context.
"""

import logging
import sys
import time
import uuid

from flask import g, request

from src.session_manager import SessionKeys as sk
from src.session_manager import SessionManager as sm

logger = logging.getLogger(__name__)


def setup_logging() -> logging.Logger:
    """Configure logging for both local development and Railway deployment."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Console handler with millisecond precision
    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Silence noisy loggers
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient.discovery").setLevel(logging.WARNING)

    return logger


def setup_request_logging(app):
    """Setup request logging hooks for the Flask application.

    Args:
        app: Flask application instance
    """
    # Paths to exclude from logging (static assets, polling endpoints)
    excluded_paths = ["/static/", "/favicon.ico", "/api/tts/status", "/sw.js", "/manifest.json"]

    def should_log() -> bool:
        """Check if current request should be logged."""
        return not any(request.path.startswith(p) or request.path == p for p in excluded_paths)

    @app.before_request
    def log_request_start():
        """Log incoming request details."""
        if not should_log():
            return

        g.request_id = str(uuid.uuid4())
        g.start_time = time.time()
        g.user_id = sm.get(sk.USER_ID)

        # Build log message
        log_parts = [
            f"REQUEST [{g.request_id}]",
            f"{request.method} {request.path}",
            f"User: {g.user_id}",
            f"IP: {request.remote_addr}",
        ]

        # Add query params if present
        if request.args:
            log_parts.append(f"Query: {dict(request.args)}")

        # Add body preview for POST/PUT/PATCH
        if request.is_json and request.method in ["POST", "PUT", "PATCH"]:
            body = str(request.get_json(silent=True))
            if len(body) > 200:
                body = body[:200] + "..."
            log_parts.append(f"Body: {body}")

        logger.info(" | ".join(log_parts))

    @app.after_request
    def log_request_end(response):
        """Log outgoing response details."""
        if not should_log():
            return response

        duration_ms = (
            round((time.time() - g.start_time) * 1000, 2) if hasattr(g, "start_time") else None
        )
        request_id = getattr(g, "request_id", "unknown")
        user_id = getattr(g, "user_id", None)
        size = len(response.get_data()) if response.get_data() else 0

        log_message = (
            f"RESPONSE [{request_id}] "
            f"Status: {response.status_code} | "
            f"Duration: {duration_ms}ms | "
            f"User: {user_id} | "
            f"Size: {size}B"
        )

        # Log at appropriate level based on status code
        if response.status_code >= 500:
            logger.error(log_message)
        elif response.status_code >= 400:
            logger.warning(log_message)
        else:
            logger.info(log_message)

        return response

    logger.info("✅ Request logging enabled")
