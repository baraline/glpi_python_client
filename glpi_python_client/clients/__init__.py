"""Public client exports for the GLPI package.

This package entrypoint exposes the supported synchronous client,
asynchronous client, and legacy v1 session wrapper without re-exporting the
internal mixin hierarchy used to implement them.
"""

from __future__ import annotations

from glpi_python_client.clients.api_v1_session import GLPIV1Session
from glpi_python_client.clients.api_v2_client import GlpiClient
from glpi_python_client.clients.async_api_v2_client import AsyncGlpiClient

__all__ = [
    "AsyncGlpiClient",
    "GLPIV1Session",
    "GlpiClient",
]
