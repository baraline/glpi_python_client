"""Asynchronous GLPI ``/Dropdowns/Location`` mixin.

The mixin exposes search, fetch, create, update, and delete helpers for the
GLPI location dropdown resource using the contract-aligned ``api_schema``
models.
"""

from __future__ import annotations

from glpi_python_client.clients.commons._constants import LOCATION_ENDPOINT, GlpiId
from glpi_python_client.clients.commons._transport import AsyncTransportMixin
from glpi_python_client.models.api_schema.dropdowns._location import (
    DeleteLocation,
    GetLocation,
    PatchLocation,
    PostLocation,
)


class AsyncLocationMixin(AsyncTransportMixin):
    """Asynchronous CRUD helpers for ``/Dropdowns/Location``."""

    async def search_locations(
        self,
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
    ) -> list[GetLocation]:
        """Search GLPI locations with an optional RSQL filter.

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL filter forwarded as the ``filter`` query parameter.
        limit : int, optional
            Maximum number of records returned by the GLPI server.
        start : int, optional
            Zero-based offset of the first record returned.

        Returns
        -------
        list[GetLocation]
            Locations matching the filter.
        """

        params: dict[str, object] = {"limit": limit, "start": start}
        if rsql_filter:
            params["filter"] = rsql_filter
        return await self._resource_list(LOCATION_ENDPOINT, GetLocation, params=params)

    async def get_location(self, location_id: GlpiId) -> GetLocation:
        """Fetch one GLPI location by identifier.

        Parameters
        ----------
        location_id : GlpiId
            Numeric identifier of the location to retrieve.

        Returns
        -------
        GetLocation
            Validated location payload.

        Raises
        ------
        ValueError
            If the GLPI server returns a non-success HTTP status.
        """

        return await self._resource_get(
            f"{LOCATION_ENDPOINT}/{location_id}",
            GetLocation,
            failure_message=f"Failed to get location {location_id}",
        )

    async def create_location(self, location: PostLocation) -> int:
        """Create one GLPI location.

        Parameters
        ----------
        location : PostLocation
            Request body describing the location to create.

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
            LOCATION_ENDPOINT,
            location,
            failure_message="Failed to create location",
            missing_message="GLPI location create response did not include an ID",
            log_message_factory=lambda new_id: f"GLPI API created location {new_id}",
        )

    async def update_location(
        self, location_id: GlpiId, location: PatchLocation
    ) -> None:
        """Update one GLPI location with a partial body.

        Parameters
        ----------
        location_id : GlpiId
            Numeric identifier of the location to update.
        location : PatchLocation
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
            f"{LOCATION_ENDPOINT}/{location_id}",
            location,
            failure_message=f"Failed to update location {location_id}",
            log_message=f"GLPI API updated location {location_id}",
        )

    async def delete_location(
        self, location_id: GlpiId, *, force: bool | None = None
    ) -> None:
        """Delete one GLPI location by identifier.

        Parameters
        ----------
        location_id : GlpiId
            Numeric identifier of the location to delete.
        force : bool | None, optional
            When ``True`` the location is permanently deleted instead of
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
            f"{LOCATION_ENDPOINT}/{location_id}",
            failure_message=f"Failed to delete location {location_id}",
            log_message=f"GLPI API deleted location {location_id}",
            force=force,
            delete_model_cls=DeleteLocation,
        )


__all__ = ["AsyncLocationMixin"]
