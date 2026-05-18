"""Custom higher-level helpers built on top of the API mixins.

The custom package exposes operations that are not advertised by the GLPI
API contract directly but are useful to client applications. Examples
include the aggregated ticket-context view and small reporting utilities
built by combining the contract-aligned CRUD helpers from
:mod:`glpi_python_client.clients.api`.

Both a synchronous mixin and an asynchronous override are provided for
the helpers that benefit from concurrent fan-out
(:mod:`glpi_python_client.clients.custom._ticket_context` and
:mod:`glpi_python_client.clients.custom._statistics`). The synchronous
mixins are composed into
:class:`~glpi_python_client.clients.GlpiClient`; the async overrides are
composed into :class:`~glpi_python_client.clients.AsyncGlpiClient`.
"""

from __future__ import annotations

from glpi_python_client.clients.custom._statistics import StatisticsMixin
from glpi_python_client.clients.custom._statistics_async import AsyncStatisticsMixin
from glpi_python_client.clients.custom._ticket_context import TicketContextMixin
from glpi_python_client.clients.custom._ticket_context_async import (
    AsyncTicketContextMixin,
)

__all__ = [
    "AsyncStatisticsMixin",
    "AsyncTicketContextMixin",
    "StatisticsMixin",
    "TicketContextMixin",
]
