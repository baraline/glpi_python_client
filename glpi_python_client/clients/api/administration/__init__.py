"""GLPI ``/Administration`` mixins for the Synchronous client.

The submodules expose the user and entity mixins used by
:class:`glpi_python_client.clients.sync_client.GlpiClient` and
:class:`glpi_python_client.clients.async_client.AsyncGlpiClient`.
"""

from __future__ import annotations

from glpi_python_client.clients.api.administration._entity import EntityMixin
from glpi_python_client.clients.api.administration._user import UserMixin

__all__ = ["EntityMixin", "UserMixin"]
