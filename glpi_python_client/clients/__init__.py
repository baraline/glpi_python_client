"""Public client exports for the GLPI Python package.

Only one client class is supported: the asynchronous
:class:`glpi_python_client.clients.glpi_client.GlpiClient`. The legacy
synchronous and dual-stack clients have been removed in favour of the
async-only design described in ``update.md``.
"""

from __future__ import annotations

from glpi_python_client.clients.glpi_client import GlpiClient

__all__ = ["GlpiClient"]
