"""GLPI ``/Administration`` mixins for the GLPI client.

The submodules expose the user and entity mixins used by this tree's
client -- :class:`glpi_python_client.AsyncGlpiClient` on the async
surface, :class:`glpi_python_client.GlpiClient` on the generated one.
"""

from __future__ import annotations

from glpi_python_client._async.clients.api.administration._entity import EntityMixin
from glpi_python_client._async.clients.api.administration._user import UserMixin

__all__ = ["EntityMixin", "UserMixin"]
