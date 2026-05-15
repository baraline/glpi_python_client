"""Custom higher-level helpers built on top of the API mixins.

The custom package exposes operations that are not advertised by the GLPI
API contract directly but are useful to client applications. Examples
include the aggregated ticket-context view and small reporting utilities
built by combining the contract-aligned CRUD helpers from
:mod:`glpi_python_client.clients.api`.
"""

from __future__ import annotations

from glpi_python_client.clients.custom._statistics import AsyncStatisticsMixin
from glpi_python_client.clients.custom._ticket_context import AsyncTicketContextMixin

__all__ = ["AsyncStatisticsMixin", "AsyncTicketContextMixin"]
