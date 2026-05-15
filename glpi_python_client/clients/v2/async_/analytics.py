"""Asynchronous analytics and context helpers for GLPI v2 clients.

This module contains the async higher-level aggregation helpers that compose
the existing public async search and record-fetch methods.
"""

from __future__ import annotations

import asyncio

from glpi_python_client.clients.v2.common.analytics import (
    build_date_range_filter,
    build_entity_search_filter,
    build_user_search_filter,
    combine_rsql_filters,
    glpi_reference_id,
    glpi_user_id,
    glpi_user_label,
    normalized_user_id_list,
    resolve_date_window,
    summarize_task_durations,
    summarize_ticket_statistics,
    unique_user_key,
)
from glpi_python_client.models import (
    GlpiEntity,
    GlpiPriority,
    GlpiTask,
    GlpiTicket,
    GlpiTicketContext,
    GlpiTicketStatus,
    GlpiTicketType,
    GlpiUser,
)

from .transport import AsyncTransportMixin


class AsyncAnalyticsMixin(AsyncTransportMixin):
    """Asynchronous GLPI analytics and ticket-context helpers.

    These methods intentionally compose the already public async low-level
    search and fetch helpers instead of bypassing them with direct transport
    calls.
    """

    async def get_ticket_context(self, ticket_id: str | int) -> GlpiTicketContext:
        """Return one grouped ticket context bundle asynchronously.

        Timeline and document list fetches are awaited concurrently once the
        primary ticket record has been scheduled.
        """

        ticket, tasks, followups, solutions, documents = await asyncio.gather(
            self.get_ticket_record(ticket_id),
            self.get_task_records(ticket_id),
            self.get_followup_records(ticket_id),
            self.get_solution_records(ticket_id),
            self.get_document_records(ticket_id),
        )
        return GlpiTicketContext(
            ticket=ticket,
            tasks=tasks,
            followups=followups,
            solutions=solutions,
            documents=documents,
        )

    async def get_task_durations(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        entity_id: int | None = None,
        entity_name: str | None = None,
        user_id: int | None = None,
        email: str | None = None,
        name: str | None = None,
        firstname: str | None = None,
        user_editor_id: int | None = None,
        user_recipient_id: int | None = None,
        default_days: int = 30,
        return_task_details: bool = False,
    ) -> dict[str, object]:
        """Return aggregated task durations for the requested date window.

        The helper uses ``search_task_records()`` as the primary data source and
        supplements tasks with ticket data only when entity or ticket-user
        filters need it.
        """

        start, end = resolve_date_window(
            start_date=start_date,
            end_date=end_date,
            default_days=default_days,
        )
        entity_ids, entity_labels = await self._resolve_entity_scope(
            entity_id=entity_id,
            entity_name=entity_name,
        )
        users = await self._resolve_users(
            user_id=user_id,
            email=email,
            name=name,
            firstname=firstname,
        )
        if (
            user_id is not None
            and any(value is not None for value in (email, name, firstname))
            and not users
        ):
            raise ValueError("The provided user filters did not match any GLPI user")
        has_user_filter = any(
            value is not None for value in (user_id, email, name, firstname)
        )
        user_ids: set[str] | None = (
            {user.user_id for user in users if user.user_id is not None}
            if has_user_filter
            else None
        )
        if user_id is not None and not any(
            value is not None for value in (email, name, firstname)
        ):
            user_ids = {str(user_id)}
            if not users:
                users = [GlpiUser(user_id=str(user_id))]

        tasks = await self.search_task_records(
            query=build_date_range_filter("date", start=start, end=end),
            fields=("content", "actiontime", "date", "tickets_id", "user", "entity"),
        )
        ticket_cache = await self._get_ticket_cache(tasks)
        filtered_tasks = [
            task
            for task in tasks
            if self._task_matches_filters(
                task,
                ticket_cache=ticket_cache,
                entity_ids=entity_ids,
                user_ids=user_ids,
                user_editor_id=str(user_editor_id)
                if user_editor_id is not None
                else None,
                user_recipient_id=str(user_recipient_id)
                if user_recipient_id is not None
                else None,
            )
        ]
        user_labels = {
            user.user_id: glpi_user_label(user)
            for user in users
            if user.user_id is not None
        }
        return summarize_task_durations(
            filtered_tasks,
            start=start,
            end=end,
            ticket_cache=ticket_cache,
            user_labels=user_labels,
            entity_labels=entity_labels,
            include_tasks=return_task_details,
        )

    async def get_ticket_statistics(
        self,
        *,
        entity_id: int | None = None,
        entity_name: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        default_days: int = 30,
        extra_filter: str | None = None,
    ) -> dict[str, object]:
        """Return ticket counts grouped by entity, status, priority, and type.

        The date window is applied to ``date_creation`` and optional extra RSQL
        filters are AND-composed onto the same ticket search.
        """

        start, end = resolve_date_window(
            start_date=start_date,
            end_date=end_date,
            default_days=default_days,
        )
        entity_ids, entity_labels = await self._resolve_entity_scope(
            entity_id=entity_id,
            entity_name=entity_name,
        )
        query = combine_rsql_filters(
            build_date_range_filter("date_creation", start=start, end=end),
            extra_filter,
        )
        tickets = await self.search_ticket_records(query=query)
        filtered_tickets = [
            ticket
            for ticket in tickets
            if entity_ids is None or glpi_reference_id(ticket.entity) in entity_ids
        ]
        return summarize_ticket_statistics(
            filtered_tickets,
            entity_labels=entity_labels,
            status_enum=GlpiTicketStatus,
            priority_enum=GlpiPriority,
            type_enum=GlpiTicketType,
        )

    async def get_user_activity(
        self,
        *,
        user_id: int | None = None,
        email: str | None = None,
        name: str | None = None,
        firstname: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        default_days: int = 30,
    ) -> dict[str, object]:
        """Return requester, technician, and task-duration activity by user.

        At least one user identifier must be supplied. Multiple matching users
        produce one entry per resolved user.
        """

        if all(value is None for value in (user_id, email, name, firstname)):
            raise ValueError("get_user_activity requires at least one user identifier")

        start, end = resolve_date_window(
            start_date=start_date,
            end_date=end_date,
            default_days=default_days,
        )
        users = await self._resolve_users(
            user_id=user_id,
            email=email,
            name=name,
            firstname=firstname,
        )
        if (
            not users
            and user_id is not None
            and email is None
            and name is None
            and firstname is None
        ):
            users = [GlpiUser(user_id=str(user_id))]
        if not users:
            return {"users": {}}

        tickets = await self.search_ticket_records(
            query=build_date_range_filter("date_creation", start=start, end=end),
        )
        tickets_with_ids = [ticket for ticket in tickets if ticket.id is not None]
        team_tasks = [
            self.get_team_member_records(ticket.id) for ticket in tickets_with_ids
        ]
        team_results = await asyncio.gather(*team_tasks)
        team_cache = {
            ticket.id: members
            for ticket, members in zip(
                tickets_with_ids,
                team_results,
                strict=True,
            )
            if ticket.id is not None
        }

        users_report: dict[str, object] = {}
        for user in users:
            resolved_user_id = glpi_user_id(user)
            label = unique_user_key(
                users_report,
                glpi_user_label(user, fallback=resolved_user_id),
                resolved_user_id,
            )
            technician_count = 0
            requester_count = 0
            for ticket in tickets:
                if glpi_user_id(ticket.user_recipient) == resolved_user_id:
                    requester_count += 1
                if ticket.id is None:
                    continue
                members = team_cache.get(ticket.id, [])
                if any(
                    member.member_type == "User"
                    and str(member.member_id) == resolved_user_id
                    for member in members
                ):
                    technician_count += 1
            users_report[label] = {
                "user_ids": normalized_user_id_list(resolved_user_id),
                "tickets_as_technician": technician_count,
                "tickets_as_recipient": requester_count,
                "task_durations": await self.get_task_durations(
                    user_id=int(resolved_user_id)
                    if resolved_user_id is not None and resolved_user_id.isdigit()
                    else None,
                    start_date=start.isoformat(),
                    end_date=end.isoformat(),
                    default_days=default_days,
                ),
            }
        return {"users": users_report}

    async def _resolve_entity_scope(
        self,
        *,
        entity_id: int | None,
        entity_name: str | None,
    ) -> tuple[set[int] | None, dict[int, str]]:
        """Resolve the entity filter inputs into IDs and labels.

        When both ``entity_id`` and ``entity_name`` are supplied, the helper
        validates that they can describe the same entity.
        """

        entity_labels: dict[int, str] = {}
        resolved_ids: set[int] | None = {entity_id} if entity_id is not None else None
        if entity_name is None:
            return resolved_ids, entity_labels

        matches = await self.search_entities(
            build_entity_search_filter(entity_name) or "",
            limit=100,
            start=0,
        )
        matched_ids: set[int] = set()
        for entity in matches:
            parsed_id = self._entity_model_id(entity)
            if parsed_id is None:
                continue
            matched_ids.add(parsed_id)
            entity_labels[parsed_id] = (
                entity.complete_name or entity.name or str(parsed_id)
            )
        if entity_id is not None:
            if not matched_ids or entity_id not in matched_ids:
                raise ValueError(
                    "entity_id and entity_name did not resolve to the same GLPI entity"
                )
            return {entity_id}, entity_labels
        return matched_ids, entity_labels

    async def _resolve_users(
        self,
        *,
        user_id: int | None,
        email: str | None,
        name: str | None,
        firstname: str | None,
    ) -> list[GlpiUser]:
        """Resolve user filters into public ``GlpiUser`` records.

        Global user lookup is used so analytics helpers can match users outside
        the client's current entity routing when necessary.
        """

        search_filter = build_user_search_filter(
            user_id=user_id,
            email=email,
            name=name,
            firstname=firstname,
        )
        if search_filter is None:
            return []
        return await self.search_users(
            search_filter,
            limit=100,
            start=0,
            skip_entity=True,
        )

    async def _get_ticket_cache(self, tasks: list[GlpiTask]) -> dict[str, GlpiTicket]:
        """Return one cache of tickets referenced by the provided task list.

        Missing or unfetchable tickets are skipped so task aggregation can
        continue with the data that is available.
        """

        ticket_ids = {task.ticket_id for task in tasks if task.ticket_id is not None}
        ticket_id_list = [
            ticket_id for ticket_id in ticket_ids if isinstance(ticket_id, str)
        ]
        fetches = [self.get_ticket_record(ticket_id) for ticket_id in ticket_id_list]
        results = await asyncio.gather(*fetches, return_exceptions=True)
        ticket_cache: dict[str, GlpiTicket] = {}
        for ticket_id, result in zip(
            ticket_id_list,
            results,
            strict=True,
        ):
            if isinstance(result, Exception):
                continue
            ticket_cache[ticket_id] = result
        return ticket_cache

    def _task_matches_filters(
        self,
        task: GlpiTask,
        *,
        ticket_cache: dict[str, GlpiTicket],
        entity_ids: set[int] | None,
        user_ids: set[str] | None,
        user_editor_id: str | None,
        user_recipient_id: str | None,
    ) -> bool:
        """Return whether one task satisfies the resolved analytics filters.

        Ticket-based filters are applied through the provided ticket cache.
        """

        if user_ids is not None and task.user_id not in user_ids:
            return False
        ticket = ticket_cache.get(task.ticket_id or "")
        entity_reference = task.entity
        if entity_reference is None and ticket is not None:
            entity_reference = ticket.entity
        if (
            entity_ids is not None
            and glpi_reference_id(entity_reference) not in entity_ids
        ):
            return False
        if user_editor_id is not None:
            if ticket is None or glpi_user_id(ticket.user_editor) != user_editor_id:
                return False
        if user_recipient_id is not None:
            if (
                ticket is None
                or glpi_user_id(ticket.user_recipient) != user_recipient_id
            ):
                return False
        return True

    def _entity_model_id(self, entity: GlpiEntity) -> int | None:
        """Return the integer identifier carried by one ``GlpiEntity`` model.

        Missing or non-numeric identifiers return ``None``.
        """

        if entity.entity_id is None or not entity.entity_id.isdigit():
            return None
        return int(entity.entity_id)
