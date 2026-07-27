"""Synchronous GLPI ``/Assistance/Ticket/{id}/Timeline/Solution`` mixin.

The mixin exposes list, fetch, create, update, and delete helpers for the
ticket solution timeline endpoint using the ``api_schema`` solution models.

Notes
-----
The live GLPI v2 server returns each entry of the list endpoint wrapped
in a ``{"type": "ITILSolution", "item": {...}}`` envelope, even though
the OpenAPI contract documents a flat array of ``ITILSolution``. Real
behaviour wins over the contract, so :func:`list_ticket_solutions`
unwraps the envelope through the shared
:meth:`~glpi_python_client.clients.commons._transport.TransportMixin._resource_list`
helper and tolerates both shapes.
"""

from __future__ import annotations

from glpi_python_client.clients.commons._constants import (
    SOLUTION_SUFFIX,
    TICKET_ENDPOINT,
    GlpiId,
)
from glpi_python_client.clients.commons._transport import TransportMixin
from glpi_python_client.models.api_schema.assistance.timeline._solution import (
    DeleteSolution,
    GetSolution,
    PatchSolution,
    PostSolution,
)


class SolutionMixin(TransportMixin):
    """Synchronous CRUD helpers for the ticket solution timeline endpoint."""

    def list_ticket_solutions(self, ticket_id: GlpiId) -> list[GetSolution]:
        """List all solutions linked to one ticket.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the parent ticket.

        Returns
        -------
        list[GetSolution]
            Solutions returned by the GLPI server, with the timeline
            envelope unwrapped where present.
        """

        return self._resource_list(
            f"{TICKET_ENDPOINT}/{ticket_id}/{SOLUTION_SUFFIX}",
            GetSolution,
            failure_message=f"Failed to list solutions for ticket {ticket_id}",
            unwrap_envelope=True,
        )

    def get_ticket_solution(
        self, ticket_id: GlpiId, solution_id: GlpiId
    ) -> GetSolution:
        """Fetch one ticket solution by identifier.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the parent ticket.
        solution_id : GlpiId
            Numeric identifier of the solution to retrieve.

        Returns
        -------
        GetSolution
            Validated solution payload.

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        return self._resource_get(
            f"{TICKET_ENDPOINT}/{ticket_id}/{SOLUTION_SUFFIX}/{solution_id}",
            GetSolution,
            failure_message=(
                f"Failed to get solution {solution_id} on ticket {ticket_id}"
            ),
        )

    def create_ticket_solution(self, ticket_id: GlpiId, solution: PostSolution) -> int:
        """Create one solution on a ticket.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the parent ticket.
        solution : PostSolution
            Request body describing the solution to create.

        Returns
        -------
        int
            Identifier assigned by the GLPI server to the new solution.

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        GlpiProtocolError
            If the create response is missing the ``id`` field.
        """

        return self._resource_create(
            f"{TICKET_ENDPOINT}/{ticket_id}/{SOLUTION_SUFFIX}",
            solution,
            failure_message=f"Failed to create solution on ticket {ticket_id}",
            missing_message="GLPI solution create response did not include an ID",
            id_keys=("id", "solution_id"),
            log_message_factory=(
                lambda new_id: f"API created solution {new_id} on ticket {ticket_id}"
            ),
        )

    def update_ticket_solution(
        self,
        ticket_id: GlpiId,
        solution_id: GlpiId,
        solution: PatchSolution,
    ) -> None:
        """Update one ticket solution with a partial body.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the parent ticket.
        solution_id : GlpiId
            Numeric identifier of the solution to update.
        solution : PatchSolution
            Partial request body.

        Returns
        -------
        None

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        self._resource_update(
            f"{TICKET_ENDPOINT}/{ticket_id}/{SOLUTION_SUFFIX}/{solution_id}",
            solution,
            failure_message=(
                f"Failed to update solution {solution_id} on ticket {ticket_id}"
            ),
            log_message=f"API updated solution {solution_id} on ticket {ticket_id}",
        )

    def delete_ticket_solution(
        self,
        ticket_id: GlpiId,
        solution_id: GlpiId,
        *,
        force: bool | None = None,
    ) -> None:
        """Delete one ticket solution by identifier.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the parent ticket.
        solution_id : GlpiId
            Numeric identifier of the solution to delete.
        force : bool | None, optional
            When ``True`` the solution is permanently deleted instead of
            being moved to the trash.

        Returns
        -------
        None

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        self._resource_delete(
            f"{TICKET_ENDPOINT}/{ticket_id}/{SOLUTION_SUFFIX}/{solution_id}",
            failure_message=(
                f"Failed to delete solution {solution_id} on ticket {ticket_id}"
            ),
            log_message=f"API deleted solution {solution_id} on ticket {ticket_id}",
            force=force,
            delete_model_cls=DeleteSolution,
        )


__all__ = ["SolutionMixin"]
