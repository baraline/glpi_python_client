"""Public exception hierarchy raised by :mod:`glpi_python_client`.

Every exception the client raises for a bad argument, an unexpected HTTP
status, an unusable response body, a network-level fault, or content it
cannot convert deliberately derives from :class:`GlpiError`, so callers can
catch the library's failure surface with a single ``except`` clause and
never need to import the underlying HTTP library.

Two deliberate exceptions to that rule remain:

* A handful of sites also deliberately still raise bare ``RuntimeError``
  (using a closed client, a missing v1 document session, a partially
  failed knowledge-base write) or ``TypeError`` (a malformed environment
  value) instead of a library type, so ``except RuntimeError`` / ``except
  TypeError`` code written against earlier releases is not broken.

:class:`GlpiStatusError`, :class:`GlpiValidationError` and
:class:`GlpiProtocolError` also inherit :class:`ValueError` so code written
against earlier releases — which raised bare ``ValueError`` — keeps working.
:class:`GlpiContentError` and :class:`GlpiTransportError` do not, for the
reason given on each: nothing was passed in wrongly.
"""

from __future__ import annotations

from functools import partial
from typing import Any


class GlpiError(Exception):
    """Base class for every exception raised by ``glpi_python_client``."""


class GlpiTransportError(GlpiError):
    """The HTTP request never produced a response.

    Raised for connection failures, DNS errors, and other network-level
    faults where GLPI returned no status code at all. The underlying
    transport exception is always attached as ``__cause__``, so the original
    fault stays available for debugging without callers having to catch it.

    Unlike most of the hierarchy this does **not** inherit ``ValueError``:
    nothing was passed in wrongly and no value came back, so the
    back-compatibility argument that applies to the status and validation
    errors does not apply here.

    Network faults are retried before they surface -- three attempts -- so
    receiving this means the fault persisted.
    """


class GlpiTimeoutError(GlpiTransportError):
    """The HTTP request exceeded its timeout before GLPI responded.

    A narrowing of :class:`GlpiTransportError` that separates "GLPI was too
    slow" from "GLPI was unreachable". Catch the parent class to handle both
    together.
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


class GlpiContentError(GlpiError):
    """A rich-text content value could not be converted.

    Raised when :class:`~glpi_python_client.content.GlpiContentConverter`
    cannot translate a value between GLPI's HTML transport format and the
    package's canonical Markdown — in either direction. The underlying
    fault is always attached as ``__cause__``.

    This exists so that no failure of the content layer escapes the
    package's taxonomy. The conversion runs third-party parsers
    (``markdownify`` inbound, ``markdown`` outbound), and a parser fault
    used to reach the caller as a bare builtin — most visibly a
    ``RecursionError``, which ``except GlpiError`` does not catch and which
    a caller reading a ticket has no reason to expect from
    ``get_ticket``. Deeply nested HTML is caught and answered with the
    body's text instead of raising at all (see
    :meth:`glpi_python_client.content.conversion.GlpiContentConverter.from_transport`);
    this is the backstop for everything else.

    Unlike :class:`GlpiStatusError`, :class:`GlpiValidationError` and
    :class:`GlpiProtocolError` this does **not** inherit ``ValueError``.
    Those three do so for back-compatibility with releases that raised
    bare ``ValueError`` at the same sites; there was never a
    ``ValueError`` here to be compatible with, and a parser exhausting the
    interpreter's stack is not a value the caller got wrong. The reasoning
    matches :class:`GlpiTransportError`.
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
    "GlpiContentError",
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
