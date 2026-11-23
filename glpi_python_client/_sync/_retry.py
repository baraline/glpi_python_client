"""Configurable retry policy shared by the v2 transport, v1 session and OAuth.

Every network-facing helper of the client retries a transient failure. The
policy is a per-client setting, not a decorator fixed at import time, so the
decorator built here reads two attributes from the object it decorates:

``_max_retries``
    Retries after the first attempt. ``0`` disables retrying.
``_retry_wait_seconds``
    Fixed pause between attempts; ``None`` selects
    :data:`DEFAULT_RETRY_WAIT_SECONDS`.

Which errors are retried is decided by each call site (``retry_on``), not by
the setting.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, TypeVar, cast

from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
)

from glpi_python_client._errors import GlpiValidationError

#: Retries after the first attempt (3 attempts in total).
DEFAULT_MAX_RETRIES = 2

#: Seconds between two attempts when no wait is configured.
DEFAULT_RETRY_WAIT_SECONDS = 3.0

F = TypeVar("F", bound=Callable[..., Any])


def validate_retry_settings(
    max_retries: object, retry_wait_seconds: object
) -> tuple[int, float | None]:
    """Return the validated ``(max_retries, retry_wait_seconds)`` pair.

    Raises
    ------
    GlpiValidationError
        If ``max_retries`` is not an integer >= 0, or ``retry_wait_seconds``
        is neither ``None`` nor a number >= 0.
    """

    if (
        isinstance(max_retries, bool)
        or not isinstance(max_retries, int)
        or max_retries < 0
    ):
        raise GlpiValidationError("max_retries must be an integer >= 0")
    if retry_wait_seconds is not None and (
        isinstance(retry_wait_seconds, bool)
        or not isinstance(retry_wait_seconds, int | float)
        or retry_wait_seconds < 0
    ):
        raise GlpiValidationError("retry_wait_seconds must be a number >= 0 or None")
    return max_retries, retry_wait_seconds


def retried(
    retry_on: type[BaseException] | tuple[type[BaseException], ...],
) -> Callable[[F], F]:
    """Retry the decorated method on ``retry_on`` per its instance's policy.

    The final error is re-raised as-is, never as ``tenacity.RetryError``.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            wait = self._retry_wait_seconds
            retrying = Retrying(
                retry=retry_if_exception_type(retry_on),
                stop=stop_after_attempt(self._max_retries + 1),
                wait=wait_fixed(DEFAULT_RETRY_WAIT_SECONDS if wait is None else wait),
                reraise=True,
            )
            return retrying(func, self, *args, **kwargs)

        return cast(F, wrapper)

    return decorator
