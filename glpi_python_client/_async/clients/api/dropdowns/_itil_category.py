"""GLPI ``/Dropdowns/ITILCategory`` mixin.

The mixin exposes search, fetch, create, update, and delete helpers for the
GLPI ITIL category dropdown resource. Every call sends the client's
``GLPI-Entity`` header (and the profile and recursion headers that travel
with it) except where a read is told to skip it with ``skip_entity=True``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from glpi_python_client._async.clients.commons._constants import (
    ITIL_CATEGORY_ENDPOINT,
    GlpiId,
)
from glpi_python_client._async.clients.commons._transport import TransportMixin
from glpi_python_client.models.api_schema.dropdowns._itil_category import (
    DeleteITILCategory,
    GetITILCategory,
    PatchITILCategory,
    PostITILCategory,
)


class ITILCategoryMixin(TransportMixin):
    """CRUD helpers for ``/Dropdowns/ITILCategory``."""

    async def search_itil_categories(
        self,
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        skip_entity: bool = False,
    ) -> list[GetITILCategory]:
        """Search GLPI ITIL categories with an optional RSQL filter.

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL filter forwarded as the ``filter`` query parameter.
        limit : int, optional
            Maximum number of records returned by the GLPI server.
        start : int, optional
            Zero-based offset of the first record returned.
        skip_entity : bool, optional
            When ``True`` the ``GLPI-Entity`` header is omitted so the
            search spans every entity the caller has access to.

        Returns
        -------
        list[GetITILCategory]
            Categories matching the filter.
        """

        params: dict[str, object] = {"limit": limit, "start": start}
        if rsql_filter:
            params["filter"] = rsql_filter
        return await self._resource_list(
            ITIL_CATEGORY_ENDPOINT,
            GetITILCategory,
            params=params,
            skip_entity=skip_entity,
        )

    async def iter_search_itil_categories(
        self,
        rsql_filter: str = "",
        *,
        batch_size: int = 50,
        skip_entity: bool = False,
    ) -> AsyncIterator[list[GetITILCategory]]:
        """Yield successive pages of GLPI ITIL categories until exhausted.

        Pagination advances the ``start`` offset after each batch and stops
        when the server returns fewer items than ``batch_size``.

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL filter forwarded as the ``filter`` query parameter.
        batch_size : int, optional
            Number of records requested per page (default 50).
        skip_entity : bool, optional
            When ``True`` the ``GLPI-Entity`` header is omitted so the
            search spans every entity the caller has access to.

        Yields
        ------
        list[GetITILCategory]
            One page per iteration. The last yielded batch may be shorter
            than ``batch_size``.
        """

        start = 0
        while True:
            batch = await self.search_itil_categories(
                rsql_filter,
                limit=batch_size,
                start=start,
                skip_entity=skip_entity,
            )
            if batch:
                yield batch
            if len(batch) < batch_size:
                break
            start += batch_size

    async def get_itil_category(
        self, category_id: GlpiId, *, skip_entity: bool = False
    ) -> GetITILCategory:
        """Fetch one GLPI ITIL category by identifier.

        Parameters
        ----------
        category_id : GlpiId
            Numeric identifier of the category to retrieve.
        skip_entity : bool, optional
            When ``True`` the ``GLPI-Entity`` header is omitted so a
            category outside the client's entity can be read.

        Returns
        -------
        GetITILCategory
            Validated category payload.

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        return await self._resource_get(
            f"{ITIL_CATEGORY_ENDPOINT}/{category_id}",
            GetITILCategory,
            failure_message=f"Failed to get ITIL category {category_id}",
            skip_entity=skip_entity,
        )

    async def create_itil_category(self, category: PostITILCategory) -> int:
        """Create one GLPI ITIL category.

        Parameters
        ----------
        category : PostITILCategory
            Request body describing the category to create.

        Returns
        -------
        int
            Identifier assigned by the GLPI server.

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        GlpiProtocolError
            If the create response is missing the ``id`` field.
        """

        return await self._resource_create(
            ITIL_CATEGORY_ENDPOINT,
            category,
            failure_message="Failed to create ITIL category",
            missing_message="GLPI ITIL category create response did not include an ID",
            log_message_factory=lambda new_id: (
                f"GLPI API created ITIL category {new_id}"
            ),
        )

    async def update_itil_category(
        self, category_id: GlpiId, category: PatchITILCategory
    ) -> None:
        """Update one GLPI ITIL category with a partial body.

        Parameters
        ----------
        category_id : GlpiId
            Numeric identifier of the category to update.
        category : PatchITILCategory
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
            f"{ITIL_CATEGORY_ENDPOINT}/{category_id}",
            category,
            failure_message=f"Failed to update ITIL category {category_id}",
            log_message=f"GLPI API updated ITIL category {category_id}",
        )

    async def delete_itil_category(
        self, category_id: GlpiId, *, force: bool | None = None
    ) -> None:
        """Delete one GLPI ITIL category by identifier.

        Parameters
        ----------
        category_id : GlpiId
            Numeric identifier of the category to delete.
        force : bool | None, optional
            When ``True`` the category is permanently deleted instead of
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
            f"{ITIL_CATEGORY_ENDPOINT}/{category_id}",
            failure_message=f"Failed to delete ITIL category {category_id}",
            log_message=f"GLPI API deleted ITIL category {category_id}",
            force=force,
            delete_model_cls=DeleteITILCategory,
        )


__all__ = ["ITILCategoryMixin"]
