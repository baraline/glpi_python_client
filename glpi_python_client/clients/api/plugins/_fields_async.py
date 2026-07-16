"""Asynchronous overrides for the Fields plugin aggregation helpers.

:meth:`get_ticket_custom_fields` and :meth:`set_ticket_custom_fields` call
sibling public methods through ``self``. Under the async bridge those
resolve to coroutine functions, so the synchronous bodies would receive
coroutine objects instead of data. These overrides await the
bridge-wrapped calls on the event loop instead.

The mixin must sit **before** :class:`PluginFieldsMixin` in the
:class:`~glpi_python_client.clients.AsyncGlpiClient` base list so the
bridge's ``__init_subclass__`` hook finds the coroutine via ``getattr``
and leaves it alone.

Every awaited call below carries ``# type: ignore[misc]``: the awaited
method (e.g. :meth:`PluginFieldsMixin.list_plugin_fields_containers`) is
declared on this mixin's own parent, so mypy resolves it statically as
the synchronous ``-> T`` method rather than the bridge-generated
coroutine it becomes at runtime on
:class:`~glpi_python_client.clients.AsyncGlpiClient`. See the matching
note in
:mod:`glpi_python_client.clients.api.knowledgebase._article_async` for
the same vocabulary, and contrast with the ``[attr-defined]`` codes in
:mod:`glpi_python_client.clients.custom._statistics_async`, where the
awaited methods are declared on a *different* mixin and mypy cannot
resolve them statically at all.
"""

from __future__ import annotations

from typing import Any

from glpi_python_client._errors import GlpiValidationError
from glpi_python_client.clients.api.plugins._fields import (
    _TICKET_ITEMTYPE,
    PluginFieldsMixin,
)
from glpi_python_client.models.api_schema.plugins import GetPluginFieldsContainer


class AsyncPluginFieldsMixin(PluginFieldsMixin):
    """Async overrides for the two Fields plugin aggregation helpers."""

    async def get_ticket_custom_fields(  # type: ignore[override]
        self, ticket_id: int
    ) -> dict[str, dict[str, Any]]:
        """Return the custom-field values defined for one ticket.

        Async override of
        :meth:`PluginFieldsMixin.get_ticket_custom_fields`; the awaited
        calls are the bridge-wrapped public helpers.

        Parameters
        ----------
        ticket_id : int
            Identifier of the ticket whose custom values are requested.

        Returns
        -------
        dict[str, dict[str, Any]]
            Per-container value mappings. Empty when the ticket has no
            stored custom values across any container.
        """

        containers = await self.list_plugin_fields_containers(  # type: ignore[misc]
            itemtype=_TICKET_ITEMTYPE
        )
        result: dict[str, dict[str, Any]] = {}
        for container in containers:
            name = container.name
            if not name:
                continue
            rows = await self.list_item_plugin_field_rows(  # type: ignore[misc]
                _TICKET_ITEMTYPE, ticket_id, name
            )
            if not rows:
                continue
            result[name] = dict(rows[0].extra_payload)
        return result

    async def set_ticket_custom_fields(  # type: ignore[override]
        self,
        ticket_id: int,
        values: dict[str, dict[str, Any]],
    ) -> None:
        """Persist custom-field values on one ticket.

        Async override of
        :meth:`PluginFieldsMixin.set_ticket_custom_fields`. Validation
        order is identical to the synchronous version: unknown containers
        and fields raise before any write.

        Parameters
        ----------
        ticket_id : int
            Identifier of the ticket whose custom values must be set.
        values : dict[str, dict[str, Any]]
            Nested mapping ``{container_name: {field_name: value}}``.

        Returns
        -------
        None
        """

        if not values:
            return

        containers = await self.list_plugin_fields_containers(  # type: ignore[misc]
            itemtype=_TICKET_ITEMTYPE
        )
        by_name: dict[str, GetPluginFieldsContainer] = {
            c.name: c for c in containers if c.name is not None
        }
        unknown = sorted(set(values) - set(by_name))
        if unknown:
            raise GlpiValidationError(
                "Unknown plugin-fields container(s) for Ticket: " + ", ".join(unknown)
            )

        for container_name, column_values in values.items():
            container = by_name[container_name]
            if container.id is None:
                raise GlpiValidationError(
                    f"Container {container_name!r} has no id; cannot write values"
                )

            declared_fields = await self.list_plugin_fields_fields(  # type: ignore[misc]
                container_id=container.id
            )
            declared = {f.name for f in declared_fields if f.name is not None}
            unknown_fields = sorted(set(column_values) - declared)
            if unknown_fields:
                raise GlpiValidationError(
                    f"Unknown field(s) for container {container_name!r}: "
                    + ", ".join(unknown_fields)
                )

            existing_rows = await self.list_item_plugin_field_rows(  # type: ignore[misc]
                _TICKET_ITEMTYPE, ticket_id, container_name
            )
            if existing_rows and existing_rows[0].id is not None:
                await self.update_item_plugin_field_row(  # type: ignore[misc, func-returns-value]
                    itemtype=_TICKET_ITEMTYPE,
                    container_name=container_name,
                    row_id=existing_rows[0].id,
                    values=column_values,
                )
            else:
                await self.create_item_plugin_field_row(  # type: ignore[misc]
                    itemtype=_TICKET_ITEMTYPE,
                    items_id=ticket_id,
                    container_id=container.id,
                    container_name=container_name,
                    values=column_values,
                )


__all__ = ["AsyncPluginFieldsMixin"]
