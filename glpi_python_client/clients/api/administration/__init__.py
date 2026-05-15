"""GLPI ``/Administration`` mixins for the asynchronous client.

The submodules expose the user and entity mixins used by
:class:`glpi_python_client.clients.glpi_client.GlpiClient`.
"""

from __future__ import annotations

from glpi_python_client.clients.api.administration._entity import AsyncEntityMixin
from glpi_python_client.clients.api.administration._user import AsyncUserMixin

__all__ = ["AsyncEntityMixin", "AsyncUserMixin"]
