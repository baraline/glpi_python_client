"""Per-endpoint API mixins backed by the ``api_schema`` Pydantic models.

The mixins under this package mirror the endpoints documented in
``docs/glpi_api_contract.json`` one for one. They wrap the Synchronous
transport helpers from :mod:`glpi_python_client.clients.commons` and exchange
typed ``Get<Name>``, ``Post<Name>``, ``Patch<Name>``, and ``Delete<Name>``
models with the GLPI API.
"""

from __future__ import annotations

from glpi_python_client.clients.api.administration import (
    EntityMixin,
    UserMixin,
)
from glpi_python_client.clients.api.assistance import (
    TeamMemberMixin,
    TicketMixin,
)
from glpi_python_client.clients.api.assistance.timeline import (
    FollowupMixin,
    SolutionMixin,
    TicketTaskMixin,
    TimelineDocumentMixin,
)
from glpi_python_client.clients.api.dropdowns import LocationMixin
from glpi_python_client.clients.api.knowledgebase import (
    KBArticleCommentMixin,
    KBArticleMixin,
    KBArticleRevisionMixin,
    KBCategoryMixin,
)
from glpi_python_client.clients.api.management import DocumentMixin
from glpi_python_client.clients.api.plugins import (
    AsyncPluginFieldsMixin,
    PluginFieldsMixin,
)

__all__ = [
    "AsyncPluginFieldsMixin",
    "DocumentMixin",
    "EntityMixin",
    "FollowupMixin",
    "KBArticleCommentMixin",
    "KBArticleMixin",
    "KBArticleRevisionMixin",
    "KBCategoryMixin",
    "LocationMixin",
    "PluginFieldsMixin",
    "SolutionMixin",
    "TeamMemberMixin",
    "TicketMixin",
    "TicketTaskMixin",
    "TimelineDocumentMixin",
    "UserMixin",
]
