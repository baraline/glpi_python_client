"""Public exception hierarchy raised by :mod:`glpi_python_client`.

Every exception the client raises for a bad argument, an unexpected HTTP
status, or an unusable response body deliberately derives from
:class:`GlpiError`, so callers can catch that part of the library surface
with a single ``except`` clause. This is not yet the library's entire
failure surface, and importing the underlying HTTP library is still
sometimes necessary:

* Network-level faults (connection failures, DNS errors, timeouts) still
  propagate as ``requests`` exceptions today. :class:`GlpiTransportError`
  and :class:`GlpiTimeoutError` are reserved for that case but are not
  raised until the httpx transport swap replaces ``requests`` (a later
  release); catch ``requests.RequestException`` alongside
  :class:`GlpiError` if you need to handle them now.
* A handful of sites also deliberately still raise bare ``RuntimeError``
  (using a closed client, a missing v1 document session, a partially
  failed knowledge-base write) or ``TypeError`` (a malformed environment
  value) instead of a library type, so ``except RuntimeError`` / ``except
  TypeError`` code written against earlier releases is not broken.

:class:`GlpiStatusError`, :class:`GlpiValidationError` and
:class:`GlpiProtocolError` also inherit :class:`ValueError` so code written
against earlier releases — which raised bare ``ValueError`` — keeps working.
"""

from __future__ import annotations

from functools import partial
from typing import Any


class GlpiError(Exception):
    """Base class for every exception raised by ``glpi_python_client``."""


class GlpiTransportError(GlpiError):
    """The HTTP request never produced a response.

    Reserved for connection failures, DNS errors, and other network-level
    faults where GLPI returned no status code at all -- but **not raised
    yet**. The client is still built on ``requests``, and those faults
    currently propagate as ``requests`` exceptions (e.g.
    ``requests.ConnectionError``) instead. This class exists for the
    httpx transport swap planned for a later release, which will raise it
    in their place; until then, catch ``requests.RequestException``
    alongside :class:`GlpiError` if you need to handle network faults.
    """


class GlpiTimeoutError(GlpiTransportError):
    """The HTTP request exceeded its timeout before GLPI responded.

    Like its parent :class:`GlpiTransportError`, this is reserved for the
    httpx transport swap and is **not raised yet**; a timeout today
    surfaces as ``requests.Timeout``.
    """


class GlpiStatusError(GlpiError, ValueError):
    """GLPI answered with an unexpected HTTP status code.

    Parameters
    ----------
    message : str
        Human-readable description of the failure.
    status_code : int
        The HTTP status code GLPI returned.
    url : str
        The absolute URL that was requested.
    response_text : str, optional
        The (possibly truncated) response body, for diagnostics.

    Attributes
    ----------
    status_code : int
        The HTTP status code GLPI returned.
    url : str
        The absolute URL that was requested.
    response_text : str
        The (possibly truncated) response body, for diagnostics.
    """

    status_code: int
    url: str
    response_text: str

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        url: str,
        response_text: str = "",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url
        self.response_text = response_text

    def __reduce__(self) -> tuple[Any, ...]:
        """Support :mod:`pickle` and :mod:`copy` for keyword-only arguments."""

        return (
            partial(
                type(self),
                status_code=self.status_code,
                url=self.url,
                response_text=self.response_text,
            ),
            (str(self),),
        )


class GlpiAuthError(GlpiStatusError):
    """GLPI rejected the credentials or the caller lacks rights (401/403)."""


class GlpiNotFoundError(GlpiStatusError):
    """GLPI has no resource at the requested URL (404)."""


class GlpiServerError(GlpiStatusError):
    """GLPI failed to serve the request (5xx). Retried by the transport."""


class GlpiValidationError(GlpiError, ValueError):
    """The caller supplied an argument or configuration the client rejects."""


class GlpiProtocolError(GlpiError, ValueError):
    """GLPI answered successfully with a body the client cannot use.

    Raised when the server returns a success status but the payload is
    missing a documented field or has an unusable shape. The caller did
    nothing wrong, so this is deliberately distinct from
    :class:`GlpiValidationError`.
    """


def status_error_class(status_code: int) -> type[GlpiStatusError]:
    """Return the most specific status-error class for one status code.

    Parameters
    ----------
    status_code : int
        The HTTP status code GLPI returned.

    Returns
    -------
    type of GlpiStatusError
        :class:`GlpiAuthError` for 401/403, :class:`GlpiNotFoundError` for
        404, :class:`GlpiServerError` for 5xx, and :class:`GlpiStatusError`
        for every other unexpected status.
    """

    if status_code in (401, 403):
        return GlpiAuthError
    if status_code == 404:
        return GlpiNotFoundError
    if 500 <= status_code < 600:
        return GlpiServerError
    return GlpiStatusError


__all__ = [
    "GlpiAuthError",
    "GlpiError",
    "GlpiNotFoundError",
    "GlpiProtocolError",
    "GlpiServerError",
    "GlpiStatusError",
    "GlpiTimeoutError",
    "GlpiTransportError",
    "GlpiValidationError",
    "status_error_class",
]
