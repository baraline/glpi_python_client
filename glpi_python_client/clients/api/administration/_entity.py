"""Synchronous GLPI ``/Administration/Entity`` mixin.

The mixin exposes the search, fetch, create, update, and delete helpers
for the GLPI entity resource. Entity calls intentionally bypass the
client's ``GLPI-Entity`` header so cross-entity lookups remain possible.
"""

from __future__ import annotations

from collections.abc import Iterator

from glpi_python_client.clients.commons._constants import ENTITY_ENDPOINT, GlpiId
from glpi_python_client.clients.commons._transport import TransportMixin
from glpi_python_client.models.api_schema.administration._entity import (
    DeleteEntity,
    GetEntity,
    PatchEntity,
    PostEntity,
)


class EntityMixin(TransportMixin):
    """Synchronous CRUD helpers for ``/Administration/Entity``."""

    def search_entities(
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
        return self._resource_list(
            ENTITY_ENDPOINT, GetEntity, params=params, skip_entity=True
        )

    def iter_search_entities(
        self,
        rsql_filter: str = "",
        *,
        batch_size: int = 50,
    ) -> Iterator[list[GetEntity]]:
        """Yield successive pages of GLPI entities until exhausted.

        The generator drives pagination automatically by advancing the
        ``start`` offset after each batch. Iteration stops when the server
        returns fewer items than ``batch_size``, which signals the last page.
        Entity calls bypass the ``GLPI-Entity`` header so cross-entity
        lookups remain possible.

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL filter forwarded as the ``filter`` query parameter.
            Empty by default, which lists every accessible entity.
        batch_size : int, optional
            Number of records requested per page (default 50).

        Yields
        ------
        list[GetEntity]
            One page of entities per iteration. The last yielded batch may
            be shorter than ``batch_size``.
        """

        start = 0
        while True:
            batch = self.search_entities(
                rsql_filter,
                limit=batch_size,
                start=start,
            )
            if batch:
                yield batch
            if len(batch) < batch_size:
                break
            start += batch_size

    def get_entity(self, entity_id: GlpiId) -> GetEntity:
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

        return self._resource_get(
            f"{ENTITY_ENDPOINT}/{entity_id}",
            GetEntity,
            failure_message=f"Failed to get entity {entity_id}",
            skip_entity=True,
        )

    def create_entity(self, entity: PostEntity) -> int:
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

        return self._resource_create(
            ENTITY_ENDPOINT,
            entity,
            failure_message="Failed to create entity",
            missing_message="GLPI entity create response did not include an ID",
            log_message_factory=lambda new_id: f"GLPI API created entity {new_id}",
            skip_entity=True,
        )

    def update_entity(self, entity_id: GlpiId, entity: PatchEntity) -> None:
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

        self._resource_update(
            f"{ENTITY_ENDPOINT}/{entity_id}",
            entity,
            failure_message=f"Failed to update entity {entity_id}",
            log_message=f"GLPI API updated entity {entity_id}",
        )

    def delete_entity(self, entity_id: GlpiId, *, force: bool | None = None) -> None:
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

        self._resource_delete(
            f"{ENTITY_ENDPOINT}/{entity_id}",
            failure_message=f"Failed to delete entity {entity_id}",
            log_message=f"GLPI API deleted entity {entity_id}",
            force=force,
            delete_model_cls=DeleteEntity,
            skip_entity=True,
        )


__all__ = ["EntityMixin"]
