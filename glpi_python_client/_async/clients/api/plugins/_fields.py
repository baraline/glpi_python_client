"""Client mixin for the GLPI ``Fields`` plugin.

The `Fields plugin <https://github.com/pluginsGLPI/fields>`_ adds
user-defined custom fields to any GLPI itemtype. It is not exposed
through the GLPI v2 REST contract so this mixin talks to the legacy v1
REST API through :class:`~glpi_python_client._async.auth._v1_session.GLPIV1Session`.

Two abstraction layers are provided:

* low-level helpers — :meth:`list_plugin_fields_containers`,
  :meth:`list_plugin_fields_fields`,
  :meth:`list_item_plugin_field_rows`,
  :meth:`update_item_plugin_field_row`,
  :meth:`create_item_plugin_field_row` — mirror one v1 endpoint each
  and stay generic across itemtypes.
* ticket-focused convenience helpers —
  :meth:`get_ticket_custom_fields` and :meth:`set_ticket_custom_fields`
  — fold the discovery + CRUD calls into a single round-trip that
  returns / accepts a ``{container_name: {field_name: value}}``
  mapping.

The value itemtype for one container is derived from the container
``name`` field with :func:`_value_itemtype_for`: container
``extrainfo`` attached to ``Ticket`` becomes
``PluginFieldsTicketextrainfo``. Field column names declared on
:class:`~glpi_python_client.models.api_schema.plugins.GetPluginFieldsField`
flow through :attr:`~glpi_python_client.models._base.GlpiModel.extra_payload`
on the value rows.
"""

from __future__ import annotations

import json
from typing import Any

from glpi_python_client._async.clients.commons._transport import TransportMixin
from glpi_python_client._errors import GlpiProtocolError, GlpiValidationError
from glpi_python_client.models.api_schema.plugins import (
    GetPluginFieldsContainer,
    GetPluginFieldsField,
    GetPluginFieldsValueRow,
)

_TICKET_ITEMTYPE = "Ticket"
_DEFAULT_LIST_RANGE = "0-999"
_V1_FEATURE_LABEL = "Fields plugin helpers"


def _value_itemtype_for(itemtype: str, container_name: str) -> str:
    """Return the value-row itemtype for a (parent itemtype, container) pair.

    The plugin uses the ``PluginFields<Itemtype><name>`` convention. The
    parent itemtype keeps its original casing and the container name is
    lower-cased to match the v1 server-side route registration.
    """

    return f"PluginFields{itemtype}{container_name.lower()}"


def _container_targets_itemtype(
    container: GetPluginFieldsContainer, itemtype: str
) -> bool:
    """Return whether ``container`` is attached to ``itemtype``.

    The v1 API returns ``itemtypes`` as a JSON-encoded string; failure
    to parse falls back to a permissive substring check.
    """

    raw = container.itemtypes
    if not raw:
        return False
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return itemtype in raw
    if isinstance(parsed, list):
        return itemtype in parsed
    return False


def _extract_row_id(payload: object) -> int:
    """Return the row id reported by the v1 API for a CRUD response.

    The v1 plugin endpoints return ``[{"<id>": true, "message": ""}]``
    where ``<id>`` is the affected row identifier. ``GlpiProtocolError``
    is raised when the payload does not match this shape.

    Raises
    ------
    GlpiProtocolError
        When ``payload`` is not a non-empty list of mappings, or no
        mapping key parses as a numeric row id.
    """

    if not isinstance(payload, list) or not payload:
        raise GlpiProtocolError(
            f"GLPI Fields plugin response missing row id: {payload!r}"
        )
    first = payload[0]
    if not isinstance(first, dict):
        raise GlpiProtocolError(
            f"GLPI Fields plugin response not a mapping: {payload!r}"
        )
    for key in first:
        if key == "message":
            continue
        try:
            return int(key)
        except (TypeError, ValueError):
            continue
    raise GlpiProtocolError(
        f"GLPI Fields plugin response did not include a numeric id: {payload!r}"
    )


class PluginFieldsMixin(TransportMixin):
    """Helpers for the GLPI ``Fields`` plugin v1 endpoints.

    Every method requires the v1 session to be configured on the client
    (see the ``v1_base_url`` and ``v1_user_token`` constructor
    arguments).
    """

    async def list_plugin_fields_containers(
        self, itemtype: str | None = None
    ) -> list[GetPluginFieldsContainer]:
        """List ``PluginFieldsContainer`` rows registered on the server.

        Parameters
        ----------
        itemtype : str | None, optional
            When provided, only the containers attached to ``itemtype``
            are returned. The filtering happens client-side because the
            v1 API stores ``itemtypes`` as a JSON-encoded string.

        Returns
        -------
        list[GetPluginFieldsContainer]
            Containers visible to the authenticated user.
        """

        v1 = self._require_v1_session(_V1_FEATURE_LABEL)
        payload = await v1.request_json(
            "GET",
            "PluginFieldsContainer",
            params={"range": _DEFAULT_LIST_RANGE},
            failure_message="Failed to list PluginFieldsContainer",
        )
        rows = payload if isinstance(payload, list) else []
        containers = [GetPluginFieldsContainer.model_validate(row) for row in rows]
        if itemtype is None:
            return containers
        return [c for c in containers if _container_targets_itemtype(c, itemtype)]

    async def list_plugin_fields_fields(
        self, container_id: int | None = None
    ) -> list[GetPluginFieldsField]:
        """List ``PluginFieldsField`` declarations.

        Parameters
        ----------
        container_id : int | None, optional
            When provided, restricts the result to the fields declared
            on this container (the filtering is performed client-side
            because the v1 API does not consistently honour the
            ``searchText`` filter on this itemtype).

        Returns
        -------
        list[GetPluginFieldsField]
            Field declarations visible to the authenticated user.
        """

        v1 = self._require_v1_session(_V1_FEATURE_LABEL)
        payload = await v1.request_json(
            "GET",
            "PluginFieldsField",
            params={"range": _DEFAULT_LIST_RANGE},
            failure_message="Failed to list PluginFieldsField",
        )
        rows = payload if isinstance(payload, list) else []
        fields = [GetPluginFieldsField.model_validate(row) for row in rows]
        if container_id is None:
            return fields
        return [f for f in fields if f.plugin_fields_containers_id == container_id]

    async def list_item_plugin_field_rows(
        self,
        itemtype: str,
        items_id: int,
        container_name: str,
    ) -> list[GetPluginFieldsValueRow]:
        """List the value rows of one container for one parent item.

        Parameters
        ----------
        itemtype : str
            Parent itemtype (e.g. ``"Ticket"``).
        items_id : int
            Identifier of the parent item.
        container_name : str
            Internal name of the container as exposed by
            :attr:`GetPluginFieldsContainer.name`.

        Returns
        -------
        list[GetPluginFieldsValueRow]
            Zero or one row depending on whether the plugin has already
            persisted any value for this item.
        """

        v1 = self._require_v1_session(_V1_FEATURE_LABEL)
        endpoint = (
            f"{itemtype}/{items_id}/{_value_itemtype_for(itemtype, container_name)}"
        )
        payload = await v1.request_json(
            "GET",
            endpoint,
            failure_message=f"Failed to list {endpoint}",
        )
        rows = payload if isinstance(payload, list) else []
        return [GetPluginFieldsValueRow.model_validate(row) for row in rows]

    async def create_item_plugin_field_row(
        self,
        *,
        itemtype: str,
        items_id: int,
        container_id: int,
        container_name: str,
        values: dict[str, object],
        entities_id: int | None = None,
    ) -> int:
        """Create one fresh plugin-fields value row.

        Parameters
        ----------
        itemtype : str
            Parent itemtype (e.g. ``"Ticket"``).
        items_id : int
            Identifier of the parent item the row is attached to.
        container_id : int
            Identifier of the originating
            :class:`GetPluginFieldsContainer`.
        container_name : str
            Internal name of the container, used to derive the value
            itemtype.
        values : dict[str, object]
            Field-name → value mapping for the dynamic columns declared
            on the container.
        entities_id : int | None, optional
            Entity to associate the row with. When omitted the GLPI
            server applies its default scope.

        Returns
        -------
        int
            Identifier of the newly created row.
        """

        v1 = self._require_v1_session(_V1_FEATURE_LABEL)
        input_payload: dict[str, object] = {
            "items_id": items_id,
            "itemtype": itemtype,
            "plugin_fields_containers_id": container_id,
            **values,
        }
        if entities_id is not None:
            input_payload["entities_id"] = entities_id
        response = await v1.request_json(
            "POST",
            _value_itemtype_for(itemtype, container_name),
            json_body={"input": input_payload},
            failure_message=(
                f"Failed to create {_value_itemtype_for(itemtype, container_name)} "
                f"row for {itemtype} {items_id}"
            ),
        )
        return _extract_row_id(response)

    async def update_item_plugin_field_row(
        self,
        *,
        itemtype: str,
        container_name: str,
        row_id: int,
        values: dict[str, object],
    ) -> None:
        """Update one existing plugin-fields value row.

        Parameters
        ----------
        itemtype : str
            Parent itemtype the container is attached to.
        container_name : str
            Internal name of the container.
        row_id : int
            Identifier of the existing value row (as returned by
            :meth:`list_item_plugin_field_rows`).
        values : dict[str, object]
            Field-name → value mapping for the columns to update. Only
            the fields supplied here are touched; the others keep their
            previous value.
        """

        v1 = self._require_v1_session(_V1_FEATURE_LABEL)
        endpoint = f"{_value_itemtype_for(itemtype, container_name)}/{row_id}"
        await v1.request_json(
            "PUT",
            endpoint,
            json_body={"input": {"id": row_id, **values}},
            failure_message=f"Failed to update {endpoint}",
        )

    async def get_ticket_custom_fields(
        self, ticket_id: int
    ) -> dict[str, dict[str, Any]]:
        """Return the custom-field values defined for one ticket.

        The result is a nested mapping shaped as
        ``{container_name: {field_name: value, ...}}``. Containers that
        do not yet have a persisted value row for the ticket are
        skipped.

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

        containers = await self.list_plugin_fields_containers(itemtype=_TICKET_ITEMTYPE)
        result: dict[str, dict[str, Any]] = {}
        for container in containers:
            name = container.name
            if not name:
                continue
            rows = await self.list_item_plugin_field_rows(
                _TICKET_ITEMTYPE, ticket_id, name
            )
            if not rows:
                continue
            result[name] = dict(rows[0].extra_payload)
        return result

    async def set_ticket_custom_fields(
        self,
        ticket_id: int,
        values: dict[str, dict[str, Any]],
    ) -> None:
        """Persist custom-field values on one ticket.

        Existing value rows are updated in place; missing rows are
        created with the supplied payload. Containers/fields that the
        server does not know about raise ``GlpiValidationError`` *before*
        any write to keep the call atomic from the caller's perspective.

        Parameters
        ----------
        ticket_id : int
            Identifier of the ticket whose custom values must be set.
        values : dict[str, dict[str, Any]]
            Nested mapping ``{container_name: {field_name: value}}``
            describing the columns to write. Container and field names
            must match what :meth:`list_plugin_fields_containers` and
            :meth:`list_plugin_fields_fields` return.
        """

        if not values:
            return

        containers = await self.list_plugin_fields_containers(itemtype=_TICKET_ITEMTYPE)
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
                raise GlpiProtocolError(
                    f"Container {container_name!r} has no id; cannot write values"
                )

            declared = {
                f.name
                for f in await self.list_plugin_fields_fields(container_id=container.id)
                if f.name is not None
            }
            unknown_fields = sorted(set(column_values) - declared)
            if unknown_fields:
                raise GlpiValidationError(
                    f"Unknown field(s) for container {container_name!r}: "
                    + ", ".join(unknown_fields)
                )

            existing_rows = await self.list_item_plugin_field_rows(
                _TICKET_ITEMTYPE, ticket_id, container_name
            )
            if existing_rows and existing_rows[0].id is not None:
                await self.update_item_plugin_field_row(
                    itemtype=_TICKET_ITEMTYPE,
                    container_name=container_name,
                    row_id=existing_rows[0].id,
                    values=column_values,
                )
            else:
                await self.create_item_plugin_field_row(
                    itemtype=_TICKET_ITEMTYPE,
                    items_id=ticket_id,
                    container_id=container.id,
                    container_name=container_name,
                    values=column_values,
                )


__all__ = ["PluginFieldsMixin"]
