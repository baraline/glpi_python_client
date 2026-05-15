"""Asynchronous GLPI ``/Administration/Entity`` mixin.

The mixin exposes the search, fetch, create, update, and delete helpers
for the GLPI entity resource. Entity calls intentionally bypass the
client's ``GLPI-Entity`` header so cross-entity lookups remain possible.
"""

from __future__ import annotations

from glpi_python_client.clients.commons._constants import ENTITY_ENDPOINT, GlpiId
from glpi_python_client.clients.commons._transport import AsyncTransportMixin
from glpi_python_client.models.api_schema.administration._entity import (
    DeleteEntity,
    GetEntity,
    PatchEntity,
    PostEntity,
)


class AsyncEntityMixin(AsyncTransportMixin):
    """Asynchronous CRUD helpers for ``/Administration/Entity``."""

    async def search_entities(
        self,
        rsql_filter: str = "",
        *,
        limit: int | None = 50,
        start: int = 0,
    ) -> list[GetEntity]:
        """Search GLPI entities with an optional RSQL filter.

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL filter forwarded as the ``filter`` query parameter.
        limit : int | None, optional
            Maximum number of records returned. ``None`` lets the GLPI
            server use its default.
        start : int, optional
            Zero-based offset of the first record returned.

        Returns
        -------
        list[GetEntity]
            Entities matching the filter.
        """

        params: dict[str, object] = {"start": start}
        if limit is not None:
            params["limit"] = limit
        if rsql_filter:
            params["filter"] = rsql_filter
        return await self._resource_list(
            ENTITY_ENDPOINT, GetEntity, params=params, skip_entity=True
        )

    async def get_entity(self, entity_id: GlpiId) -> GetEntity:
        """Fetch one GLPI entity by identifier.

        Parameters
        ----------
        entity_id : GlpiId
            Numeric identifier of the entity to retrieve.

        Returns
        -------
        GetEntity
            Validated entity payload.

        Raises
        ------
        ValueError
            If the GLPI server returns a non-success HTTP status.
        """

        return await self._resource_get(
            f"{ENTITY_ENDPOINT}/{entity_id}",
            GetEntity,
            failure_message=f"Failed to get entity {entity_id}",
            skip_entity=True,
        )

    async def create_entity(self, entity: PostEntity) -> int:
        """Create one GLPI entity.

        Parameters
        ----------
        entity : PostEntity
            Request body describing the entity to create.

        Returns
        -------
        int
            Identifier assigned by the GLPI server.

        Raises
        ------
        ValueError
            If the create response is missing ``id`` or returns a
            non-success HTTP status.
        """

        return await self._resource_create(
            ENTITY_ENDPOINT,
            entity,
            failure_message="Failed to create entity",
            missing_message="GLPI entity create response did not include an ID",
            log_message_factory=lambda new_id: f"GLPI API created entity {new_id}",
            skip_entity=True,
        )

    async def update_entity(self, entity_id: GlpiId, entity: PatchEntity) -> None:
        """Update one GLPI entity with a partial body.

        Parameters
        ----------
        entity_id : GlpiId
            Numeric identifier of the entity to update.
        entity : PatchEntity
            Partial request body.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If the GLPI server returns a non-success HTTP status.
        """

        await self._resource_update(
            f"{ENTITY_ENDPOINT}/{entity_id}",
            entity,
            failure_message=f"Failed to update entity {entity_id}",
            log_message=f"GLPI API updated entity {entity_id}",
        )

    async def delete_entity(
        self, entity_id: GlpiId, *, force: bool | None = None
    ) -> None:
        """Delete one GLPI entity by identifier.

        Parameters
        ----------
        entity_id : GlpiId
            Numeric identifier of the entity to delete.
        force : bool | None, optional
            When ``True`` the entity is permanently deleted instead of
            being moved to the trash.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If the GLPI server returns a non-success HTTP status.
        """

        await self._resource_delete(
            f"{ENTITY_ENDPOINT}/{entity_id}",
            failure_message=f"Failed to delete entity {entity_id}",
            log_message=f"GLPI API deleted entity {entity_id}",
            force=force,
            delete_model_cls=DeleteEntity,
            skip_entity=True,
        )


__all__ = ["AsyncEntityMixin"]
