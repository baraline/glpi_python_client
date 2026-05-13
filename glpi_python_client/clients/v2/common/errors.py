"""Error formatting helpers for GLPI v2 client operations.

These helpers normalize exception messages so retry wrappers and direct remote
call failures surface a readable error string to higher-level client methods.
"""

from __future__ import annotations

from tenacity import RetryError


def remote_error_message(exc: Exception) -> str:
    """Return a readable message for one remote-call exception.

    ``tenacity.RetryError`` instances are unwrapped to expose the underlying
    failure message instead of the retry wrapper representation.
    """

    if isinstance(exc, RetryError):
        inner_exception = exc.last_attempt.exception()
        if isinstance(inner_exception, Exception):
            return str(inner_exception)
    return str(exc)
