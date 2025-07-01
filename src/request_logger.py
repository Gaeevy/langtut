"""
Request logging utility for Flask application.

Provides comprehensive request/response logging with correlation IDs, timing,
and user context for all incoming requests.
"""

import logging
import time
import uuid
from typing import Any

from flask import g, request

from src.session_manager import SessionKeys as sk
from src.session_manager import SessionManager as sm

# Create logger for request tracking
logger = logging.getLogger(__name__)


def get_current_user_id_from_session() -> int | None:
    """
    Extract current user ID from session using existing session manager.

    Returns:
        User ID if authenticated, None otherwise
    """
    try:
        return sm.get(sk.USER_ID)
    except Exception:
        # If session access fails, return None
        return None


def should_log_request() -> bool:
    """
    Determine if we should log this request.

    Returns:
        True if request should be logged, False for static assets
    """
    # Return True if we should log, False for static assets and favicon
    return not (request.path.startswith('/static/') or request.path == '/favicon.ico')


def safe_get_request_body() -> Any:
    """
    Safely extract request body with error handling.

    Returns:
        Request body as dict/list if JSON, string for other types, or None if unable to parse
    """
    try:
        # Only try to get JSON if content type suggests it
        if request.content_type and 'application/json' in request.content_type:
            return request.get_json(silent=True)

        # For form data
        if request.content_type and 'application/x-www-form-urlencoded' in request.content_type:
            return dict(request.form)

        # For other data types, return raw data as string (truncated for safety)
        if request.data:
            raw_data = request.data.decode('utf-8', errors='ignore')
            return raw_data[:1000] if len(raw_data) > 1000 else raw_data

        return None

    except Exception as e:
        logger.warning(f'Could not parse request body: {e}')
        return None


def log_request_ingress() -> None:
    """
    Log incoming request details (ingress).

    Sets up request correlation and logs comprehensive request information.
    """
    if not should_log_request():
        return

    # Set up request correlation
    g.request_id = str(uuid.uuid4())
    g.start_time = time.time()
    g.user_id = get_current_user_id_from_session()

    # Build detailed log message
    request_body = safe_get_request_body()
    query_params = dict(request.args)

    log_message = (
        f'REQUEST_START [{g.request_id}] '
        f'{request.method} {request.path} | '
        f'User: {g.user_id} | '
        f'IP: {request.remote_addr} | '
        f'Endpoint: {request.endpoint}'
    )

    # Add query params if present
    if query_params:
        log_message += f' | Query: {query_params}'

    # Add request body if present
    if request_body:
        # Truncate body for readability if it's too long
        body_str = str(request_body)
        if len(body_str) > 200:
            body_str = body_str[:200] + '...'
        log_message += f' | Body: {body_str}'

    # Add content type if present
    if request.content_type:
        log_message += f' | Content-Type: {request.content_type}'

    logger.info(log_message)


def log_request_egress(response) -> None:
    """
    Log outgoing response details (egress).

    Args:
        response: Flask response object

    Calculates request duration and logs response information.
    """
    if not should_log_request():
        return

    # Calculate request duration
    duration_ms = None
    if hasattr(g, 'start_time'):
        duration_ms = round((time.time() - g.start_time) * 1000, 2)

    # Build detailed log message
    request_id = getattr(g, 'request_id', 'unknown')
    user_id = getattr(g, 'user_id', None)
    response_size = len(response.get_data()) if response.get_data() else 0

    log_message = (
        f'REQUEST_END [{request_id}] '
        f'Status: {response.status_code} | '
        f'Duration: {duration_ms}ms | '
        f'User: {user_id} | '
        f'Size: {response_size}B'
    )

    # Add content type if present
    if response.content_type:
        log_message += f' | Content-Type: {response.content_type}'

    # Log at different levels based on status code
    if response.status_code >= 500:
        logger.error(log_message)
    elif response.status_code >= 400:
        logger.warning(log_message)
    else:
        logger.info(log_message)


def setup_request_logging(app):
    """
    Set up request logging hooks for the Flask application.

    Args:
        app: Flask application instance
    """

    @app.before_request
    def before_request_handler():
        """Handle request ingress logging."""
        try:
            log_request_ingress()
        except Exception as e:
            # Don't let logging errors break the request
            logger.error(f'Error in request ingress logging: {e}', exc_info=True)

    @app.after_request
    def after_request_handler(response):
        """Handle request egress logging."""
        try:
            log_request_egress(response)
        except Exception as e:
            # Don't let logging errors break the response
            logger.error(f'Error in request egress logging: {e}', exc_info=True)
        return response

    logger.info('✅ Request logging hooks installed')
