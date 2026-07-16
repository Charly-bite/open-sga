"""
Shared Flask extensions — created here to avoid circular imports.
Initialized with ``init_app`` by the application factory in app.py.
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],  # No global limit; applied per-route
    storage_uri="memory://",
)
