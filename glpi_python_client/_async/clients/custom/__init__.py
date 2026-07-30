"""Higher-level helpers built on top of the API mixins.

The custom package exposes operations the GLPI API contract does not
advertise directly but which client applications need: the aggregated
ticket-context view and the reporting helpers, both assembled from the
contract-aligned CRUD helpers in
:mod:`glpi_python_client._async.clients.api`.

Each helper is written once. The fan-out points call ``gather`` from
:mod:`glpi_python_client._async._concurrency`, which runs them
concurrently on the async surface and sequentially on the generated one
-- so there is no second copy of this logic to keep in step.
"""

from __future__ import annotations

from glpi_python_client._async.clients.custom._statistics import StatisticsMixin
from glpi_python_client._async.clients.custom._ticket_context import TicketContextMixin

__all__ = [
    "StatisticsMixin",
    "TicketContextMixin",
]
