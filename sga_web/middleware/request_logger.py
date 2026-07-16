"""
SGA Request Logger Middleware

Structured logging for every HTTP request. Provides:
- Request method, path, status code, response time
- Authenticated user info
- Client IP address
- Structured format for easy parsing and monitoring
"""

import time
import logging
from flask import request, g
from flask_login import current_user

logger = logging.getLogger("sga.requests")


def init_request_logger(app):
    """Register request logging hooks on the Flask app.

    Usage in app.py:
        from middleware.request_logger import init_request_logger
        init_request_logger(app)
    """

    @app.before_request
    def _start_timer():
        g.request_start_time = time.time()

    @app.after_request
    def _log_request(response):
        # Skip logging for static files and health checks
        if request.path.startswith("/static/") or request.path == "/favicon.ico":
            return response

        duration_ms = round(
            (time.time() - getattr(g, "request_start_time", time.time())) * 1000, 1
        )

        user = "anonymous"
        if (
            current_user
            and hasattr(current_user, "is_authenticated")
            and current_user.is_authenticated
        ):
            user = getattr(current_user, "username", str(current_user.get_id()))

        # Color-code by status for terminal readability
        status = response.status_code
        if status >= 500:
            log_fn = logger.error
        elif status >= 400:
            log_fn = logger.warning
        else:
            log_fn = logger.info

        log_fn(
            "%s %s -> %d (%sms) [user=%s, ip=%s]",
            request.method,
            request.path,
            status,
            duration_ms,
            user,
            request.remote_addr,
        )

        return response
