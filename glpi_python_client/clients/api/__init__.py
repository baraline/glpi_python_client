"""Per-endpoint API mixins backed by the ``api_schema`` Pydantic models.

The mixins under this package mirror the endpoints documented in
``docs/glpi_api_contract.json`` one for one. They wrap the asynchronous
transport helpers from :mod:`glpi_python_client.clients.commons` and exchange
typed ``Get<Name>``, ``Post<Name>``, ``Patch<Name>``, and ``Delete<Name>``
models with the GLPI API.
"""

from __future__ import annotations

from glpi_python_client.clients.api.administration import (
    AsyncEntityMixin,
    AsyncUserMixin,
)
from glpi_python_client.clients.api.assistance import (
    AsyncTeamMemberMixin,
    AsyncTicketMixin,
)
from glpi_python_client.clients.api.assistance.timeline import (
    AsyncFollowupMixin,
    AsyncSolutionMixin,
    AsyncTicketTaskMixin,
    AsyncTimelineDocumentMixin,
)
from glpi_python_client.clients.api.dropdowns import AsyncLocationMixin
from glpi_python_client.clients.api.management import AsyncDocumentMixin

__all__ = [
    "AsyncDocumentMixin",
    "AsyncEntityMixin",
    "AsyncFollowupMixin",
    "AsyncLocationMixin",
    "AsyncSolutionMixin",
    "AsyncTeamMemberMixin",
    "AsyncTicketMixin",
    "AsyncTicketTaskMixin",
    "AsyncTimelineDocumentMixin",
    "AsyncUserMixin",
]
