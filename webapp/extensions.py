"""Shared Flask extension instances.

Keeping the limiter here (rather than in ``app.py``) lets route modules import
it without creating a circular import with the application module.
"""

from flask import request
from flask_limiter import Limiter


def _client_key():
    return request.remote_addr or "unknown"


# In-memory storage is intentional: the app runs as a single worker.
limiter = Limiter(
    key_func=_client_key,
    default_limits=None,
    storage_uri="memory://",
)
