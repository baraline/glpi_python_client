"""Unit tests for :func:`remote_error_message`."""

from __future__ import annotations

from concurrent.futures import Future

from tenacity import RetryError

from glpi_python_client.clients.commons._errors import remote_error_message


def _make_retry_error(inner: Exception) -> RetryError:
    """Wrap ``inner`` in a ``tenacity.RetryError`` for testing."""

    future: Future[object] = Future()
    future.set_exception(inner)
    return RetryError(future)


def test_remote_error_message_returns_plain_str_for_regular_exception() -> None:
    """Non-retry exceptions are stringified directly."""

    assert remote_error_message(ValueError("boom")) == "boom"


def test_remote_error_message_unwraps_retry_error() -> None:
    """``RetryError`` exposes the underlying failure message."""

    inner = RuntimeError("network down")
    wrapped = _make_retry_error(inner)
    assert remote_error_message(wrapped) == "network down"


def test_remote_error_message_falls_back_when_inner_is_missing() -> None:
    """A ``RetryError`` without a real inner exception falls back to ``str``."""

    future: Future[object] = Future()
    future.set_result("ok")
    wrapped = RetryError(future)
    # The inner attempt did not raise, so the helper falls back to str(exc).
    assert remote_error_message(wrapped) == str(wrapped)
