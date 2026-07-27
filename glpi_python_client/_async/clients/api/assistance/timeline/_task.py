"""GLPI ``/Assistance/Ticket/{id}/Timeline/Task`` mixin.

The mixin exposes list, fetch, create, update, and delete helpers for the
ticket task timeline endpoint using the contract-aligned ``api_schema``
ticket-task models.

Notes
-----
The live GLPI v2 server returns each entry of the list endpoint wrapped
in a ``{"type": "Task", "item": {...}}`` envelope, even though the
OpenAPI contract documents a flat array of ``TicketTask``. Real behaviour
wins over the contract, so :func:`list_ticket_tasks` unwraps the envelope
through the shared
:meth:`~glpi_python_client._async.clients.commons._transport.TransportMixin._resource_list`
helper and tolerates both shapes.
"""

from __future__ import annotations

from glpi_python_client._async.clients.commons._constants import (
    TASK_SUFFIX,
    TICKET_ENDPOINT,
    GlpiId,
)
from glpi_python_client._async.clients.commons._transport import TransportMixin
from glpi_python_client.models.api_schema.assistance.timeline._task import (
    DeleteTicketTask,
    GetTicketTask,
    PatchTicketTask,
    PostTicketTask,
)


class TicketTaskMixin(TransportMixin):
    """CRUD helpers for the ticket task timeline endpoint."""

    async def list_ticket_tasks(self, ticket_id: GlpiId) -> list[GetTicketTask]:
        """List all tasks linked to one ticket.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the parent ticket.

        Returns
        -------
        list[GetTicketTask]
            Tasks returned by the GLPI server, with the timeline envelope
            unwrapped where present.
        """

        return await self._resource_list(
            f"{TICKET_ENDPOINT}/{ticket_id}/{TASK_SUFFIX}",
            GetTicketTask,
            failure_message=f"Failed to list tasks for ticket {ticket_id}",
            unwrap_envelope=True,
        )

    async def get_ticket_task(
        self, ticket_id: GlpiId, task_id: GlpiId
    ) -> GetTicketTask:
        """Fetch one ticket task by identifier.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the parent ticket.
        task_id : GlpiId
            Numeric identifier of the task to retrieve.

        Returns
        -------
        GetTicketTask
            Validated task payload.

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        return await self._resource_get(
            f"{TICKET_ENDPOINT}/{ticket_id}/{TASK_SUFFIX}/{task_id}",
            GetTicketTask,
            failure_message=f"Failed to get task {task_id} on ticket {ticket_id}",
        )

    async def create_ticket_task(self, ticket_id: GlpiId, task: PostTicketTask) -> int:
        """Create one task on a ticket.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the parent ticket.
        task : PostTicketTask
            Request body describing the task to create.

        Returns
        -------
        int
            Identifier assigned by the GLPI server to the new task.

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        GlpiProtocolError
            If the create response is missing the ``id`` field.
        """

        return await self._resource_create(
            f"{TICKET_ENDPOINT}/{ticket_id}/{TASK_SUFFIX}",
            task,
            failure_message=f"Failed to create task on ticket {ticket_id}",
            missing_message="GLPI task create response did not include an ID",
            id_keys=("id", "task_id"),
            log_message_factory=(
                lambda new_id: f"GLPI API created task {new_id} on ticket {ticket_id}"
            ),
        )

    async def update_ticket_task(
        self,
        ticket_id: GlpiId,
        task_id: GlpiId,
        task: PatchTicketTask,
    ) -> None:
        """Update one ticket task with a partial body.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the parent ticket.
        task_id : GlpiId
            Numeric identifier of the task to update.
        task : PatchTicketTask
            Partial request body.

        Returns
        -------
        None

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        await self._resource_update(
            f"{TICKET_ENDPOINT}/{ticket_id}/{TASK_SUFFIX}/{task_id}",
            task,
            failure_message=f"Failed to update task {task_id} on ticket {ticket_id}",
            log_message=f"GLPI API updated task {task_id} on ticket {ticket_id}",
        )

    async def delete_ticket_task(
        self,
        ticket_id: GlpiId,
        task_id: GlpiId,
        *,
        force: bool | None = None,
    ) -> None:
        """Delete one ticket task by identifier.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the parent ticket.
        task_id : GlpiId
            Numeric identifier of the task to delete.
        force : bool | None, optional
            When ``True`` the task is permanently deleted instead of
            being moved to the trash.

        Returns
        -------
        None

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        await self._resource_delete(
            f"{TICKET_ENDPOINT}/{ticket_id}/{TASK_SUFFIX}/{task_id}",
            failure_message=f"Failed to delete task {task_id} on ticket {ticket_id}",
            log_message=f"GLPI API deleted task {task_id} on ticket {ticket_id}",
            force=force,
            delete_model_cls=DeleteTicketTask,
        )


__all__ = ["TicketTaskMixin"]
