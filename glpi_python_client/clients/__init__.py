"""Public client exports for the GLPI Python package.

The package exposes two client classes:

* :class:`GlpiClient` — synchronous, blocking client. The single source
  of truth for endpoint behaviour.
* :class:`AsyncGlpiClient` — asynchronous facade that wraps every
  synchronous method into a coroutine via
  :class:`~glpi_python_client.clients.commons._async_bridge.AsyncBridge`.

Both classes share the same endpoint surface; pick the one matching
your runtime model.
"""

from __future__ import annotations

from glpi_python_client.clients.async_client import AsyncGlpiClient
from glpi_python_client.clients.sync_client import GlpiClient

__all__ = ["AsyncGlpiClient", "GlpiClient"]
