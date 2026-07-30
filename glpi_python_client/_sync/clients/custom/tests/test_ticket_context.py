"""Unit tests for the ticket-context mixin.

The tests stub ``_get_request`` on a real client so
:meth:`~glpi_python_client._sync.clients.custom._ticket_context.TicketContextMixin.get_ticket_context`
exercises its real aggregation logic without any network call.
"""

from __future__ import annotations

from typing import Any

from glpi_python_client._sync._testing import make_client
from glpi_python_client.testing.utils import FakeResponse


def test_get_ticket_context_assembles_ticket_and_timeline() -> None:
    """``get_ticket_context`` fetches one ticket and four timeline lists.

    The method must call ``get_ticket`` once and one list helper for each
    timeline resource (tasks, followups, solutions, documents), then
    bundle all results into a single :class:`GlpiTicketContext`.
    """

    client = make_client()
    calls: list[str] = []

    def _get(
        endpoint: str,
        params: Any = None,
        skip_entity: bool = False,
    ) -> FakeResponse:
        calls.append(endpoint)
        if endpoint.endswith("/Timeline/Task"):
            return FakeResponse(status_code=200, payload=[])
        if endpoint.endswith("/Timeline/Followup"):
            return FakeResponse(status_code=200, payload=[])
        if endpoint.endswith("/Timeline/Solution"):
            return FakeResponse(status_code=200, payload=[])
        if endpoint.endswith("/Timeline/Document"):
            return FakeResponse(status_code=200, payload=[])
        # Primary ticket fetch.
        return FakeResponse(
            status_code=200,
            payload={"id": 42, "name": "Test ticket", "content": "<p>body</p>"},
        )

    client._get_request = _get  # type: ignore[method-assign]
    ctx = client.get_ticket_context(42)

    assert ctx.ticket.id == 42
    assert ctx.tasks == []
    assert ctx.followups == []
    assert ctx.solutions == []
    assert ctx.documents == []
    # Five separate GET calls must have been dispatched.
    assert len(calls) == 5

    client.close()
