"""Parity tests asserting that the sync and async clients expose the same surface.

These tests guarantee that any public method added to the sync mixins is
automatically reflected on the async client through
:class:`~glpi_python_client.clients.commons._async_bridge.AsyncBridge`
without requiring a parallel async implementation, and conversely that
the async client does not gain methods the sync client lacks.
"""

from __future__ import annotations

import inspect

from glpi_python_client import AsyncGlpiClient, GlpiClient


def _public_callable_names(cls: type) -> set[str]:
    """Return the public method names exposed by ``cls``.

    Lifecycle helpers that intentionally differ between the sync and
    async surfaces are filtered out.
    """

    excluded = {"from_env", "close"}
    return {
        name
        for name, member in inspect.getmembers(cls, predicate=callable)
        if not name.startswith("_") and name not in excluded
    }


def test_sync_and_async_clients_expose_the_same_public_methods() -> None:
    """The async client must expose exactly the same endpoint methods."""

    sync_names = _public_callable_names(GlpiClient)
    async_names = _public_callable_names(AsyncGlpiClient)
    assert sync_names == async_names


def test_sync_endpoint_methods_are_not_coroutine_functions() -> None:
    """Every public sync method is a plain or generator function, not a coroutine."""

    for name in _public_callable_names(GlpiClient):
        member = getattr(GlpiClient, name)
        assert not inspect.iscoroutinefunction(member), (
            f"GlpiClient.{name} should be synchronous"
        )
        assert not inspect.isasyncgenfunction(member), (
            f"GlpiClient.{name} should be synchronous"
        )


def test_async_endpoint_methods_are_coroutine_functions() -> None:
    """Every public async method is a coroutine or async generator function."""

    for name in _public_callable_names(AsyncGlpiClient):
        member = getattr(AsyncGlpiClient, name)
        is_async = inspect.iscoroutinefunction(member) or inspect.isasyncgenfunction(
            member
        )
        assert is_async, (
            f"AsyncGlpiClient.{name} should be a coroutine or async generator"
        )


def test_async_client_close_is_coroutine_and_sync_is_not() -> None:
    """Lifecycle helpers differ on purpose between the two surfaces."""

    assert not inspect.iscoroutinefunction(GlpiClient.close)
    assert inspect.iscoroutinefunction(AsyncGlpiClient.close)
