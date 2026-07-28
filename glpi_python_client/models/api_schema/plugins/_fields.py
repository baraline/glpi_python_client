"""GLPI ``Fields`` plugin schemas exposed through the v1 REST API.

The `GLPI Fields plugin <https://github.com/pluginsGLPI/fields>`_ adds
user-defined custom fields to any GLPI itemtype (tickets, computers,
problems, ...). It is configured through two top-level itemtypes:

* :class:`GetPluginFieldsContainer` — one container per "tab" or "block"
  added to an itemtype (e.g. an ``Extra information`` tab on
  ``Ticket``).
* :class:`GetPluginFieldsField` — one user-defined field declaration
  belonging to a container (the column name, type, default value, ...).

For each container, the plugin creates a dedicated itemtype that stores
one row per "item + container" pair. The itemtype name is built as
``PluginFields<Itemtype><ContainerName>`` (e.g.
``PluginFieldsTicketextrainfo`` for an ``extrainfo``
container attached to ``Ticket``). Rows from those itemtypes are modelled
by :class:`GetPluginFieldsValueRow` — the actual field columns are
dynamic so they flow through the ``extra_payload`` escape hatch on
:class:`~glpi_python_client.models._base.GlpiModel`.
"""

from __future__ import annotations

from glpi_python_client.models._base import GlpiModel


class GetPluginFieldsContainer(GlpiModel):
    """One ``PluginFieldsContainer`` row returned by the v1 REST API.

    Parameters
    ----------
    id : int | None, optional
        Native identifier of the container.
    name : str | None, optional
        Internal name used to derive the value itemtype
        (``PluginFields<Itemtype><name>``).
    label : str | None, optional
        Human-readable label shown in the GLPI UI.
    itemtypes : str | None, optional
        JSON-encoded list of itemtypes the container is attached to (the
        v1 API returns it as a string, e.g. ``'["Ticket"]'``).
    type : str | None, optional
        Container kind (``"tab"``, ``"dom"``, ``"domtab"``, ...).
    subtype : str | None, optional
        Optional sub-discriminator returned by the plugin.
    entities_id : int | None, optional
        Identifier of the entity the container belongs to.
    is_recursive : bool | None, optional
        Whether the container is visible in child entities.
    is_active : bool | None, optional
        Whether the container is enabled.
    """

    id: int | None = None
    name: str | None = None
    label: str | None = None
    itemtypes: str | None = None
    type: str | None = None
    subtype: str | None = None
    entities_id: int | None = None
    is_recursive: bool | None = None
    is_active: bool | None = None


class GetPluginFieldsField(GlpiModel):
    """One ``PluginFieldsField`` row returned by the v1 REST API.

    Parameters
    ----------
    id : int | None, optional
        Native identifier of the field declaration.
    name : str | None, optional
        Column name used inside the per-item value row (this is the key
        appearing in :attr:`GetPluginFieldsValueRow.extra_payload`).
    label : str | None, optional
        Human-readable label shown in the GLPI UI.
    type : str | None, optional
        Field type (``"string"``, ``"text"``, ``"richtext"``,
        ``"dropdown"``, ``"yesno"``, ``"date"``, ``"datetime"``,
        ``"number"``, ``"url"``, ``"header"``, ...).
    plugin_fields_containers_id : int | None, optional
        Identifier of the parent :class:`GetPluginFieldsContainer`.
    ranking : int | None, optional
        Display ordering of the field inside its container.
    default_value : str | None, optional
        Default value applied when a fresh row is created.
    is_active : bool | None, optional
        Whether the field declaration is enabled.
    is_readonly : bool | None, optional
        Whether the field is read-only in the GLPI UI.
    mandatory : bool | None, optional
        Whether the field is required when the parent item is saved.
    multiple : bool | None, optional
        Whether the field accepts multiple values (dropdown only).
    allowed_values : str | None, optional
        Newline-separated list of accepted values for some field types
        (the v1 API returns the raw text payload).
    """

    id: int | None = None
    name: str | None = None
    label: str | None = None
    type: str | None = None
    plugin_fields_containers_id: int | None = None
    ranking: int | None = None
    default_value: str | None = None
    is_active: bool | None = None
    is_readonly: bool | None = None
    mandatory: bool | None = None
    multiple: bool | None = None
    allowed_values: str | None = None


class GetPluginFieldsValueRow(GlpiModel):
    """One ``PluginFields<Itemtype><Container>`` row keyed by parent item.

    The actual field columns (``<name>`` from each
    :class:`GetPluginFieldsField`) are dynamic per container and so are
    collected into :attr:`GlpiModel.extra_payload` rather than declared
    here.

    Parameters
    ----------
    id : int | None, optional
        Native identifier of the value row.
    items_id : int | None, optional
        Identifier of the parent GLPI item the row is attached to.
    itemtype : str | None, optional
        Itemtype of the parent GLPI item (e.g. ``"Ticket"``).
    plugin_fields_containers_id : int | None, optional
        Identifier of the originating
        :class:`GetPluginFieldsContainer`.
    entities_id : int | None, optional
        Identifier of the entity the row belongs to.
    """

    id: int | None = None
    items_id: int | None = None
    itemtype: str | None = None
    plugin_fields_containers_id: int | None = None
    entities_id: int | None = None


class PostPluginFieldsValueRow(GlpiModel):
    """Request body used to create a fresh plugin-fields value row.

    The dynamic field columns are passed through
    :attr:`GlpiModel.extra_payload` so each container can supply its own
    column names without a tailored Pydantic model.

    Parameters
    ----------
    items_id : int
        Identifier of the parent GLPI item the row is attached to.
    itemtype : str
        Itemtype of the parent GLPI item (e.g. ``"Ticket"``).
    plugin_fields_containers_id : int
        Identifier of the originating
        :class:`GetPluginFieldsContainer`.
    entities_id : int | None, optional
        Identifier of the entity the row should be linked to. When
        omitted GLPI applies its default scope.
    """

    items_id: int
    itemtype: str
    plugin_fields_containers_id: int
    entities_id: int | None = None


__all__ = [
    "GetPluginFieldsContainer",
    "GetPluginFieldsField",
    "GetPluginFieldsValueRow",
    "PostPluginFieldsValueRow",
]
