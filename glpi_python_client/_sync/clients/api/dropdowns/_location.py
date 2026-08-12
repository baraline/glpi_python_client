"""GLPI ``/Dropdowns/Location`` mixin.

The mixin exposes search, fetch, create, update, and delete helpers for the
GLPI location dropdown resource using the contract-aligned ``api_schema``
models.
"""

from __future__ import annotations

from collections.abc import Iterator

from glpi_python_client._sync.clients.commons._constants import (
    LOCATION_ENDPOINT,
    GlpiId,
)
from glpi_python_client._sync.clients.commons._transport import TransportMixin
from glpi_python_client.models.api_schema.dropdowns._location import (
    DeleteLocation,
    GetLocation,
    PatchLocation,
    PostLocation,
)


class LocationMixin(TransportMixin):
    """CRUD helpers for ``/Dropdowns/Location``."""

    def search_locations(
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
        return self._resource_list(LOCATION_ENDPOINT, GetLocation, params=params)

    def iter_search_locations(
        self,
        rsql_filter: str = "",
        *,
        batch_size: int = 50,
    ) -> Iterator[list[GetLocation]]:
        """Yield successive pages of GLPI locations until exhausted.

        The generator drives pagination automatically by advancing the
        ``start`` offset after each batch. Iteration stops when the server
        returns fewer items than ``batch_size``, which signals the last page.

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL filter forwarded as the ``filter`` query parameter.
            Empty by default, which lists every visible record.
        batch_size : int, optional
            Number of records requested per page (default 50). Acts as the
            ``limit`` parameter on each underlying :meth:`search_locations`
            call.

        Notes
        -----
        A 4xx response is swallowed by the underlying search helper, which
        returns ``[]``. Because iteration stops on a page shorter than
        ``batch_size``, a 4xx on the first page ends the walk having yielded
        nothing -- indistinguishable from a filter that matched nothing.
        Check the caller's permissions and entity scope before reading an
        empty walk as an empty result set. 5xx still raises.

        Yields
        ------
        list[GetLocation]
            One page per iteration. The last yielded batch may be shorter
            than ``batch_size``.
        """

        start = 0
        while True:
            batch = self.search_locations(
                rsql_filter,
                limit=batch_size,
                start=start,
            )
            if batch:
                yield batch
            if len(batch) < batch_size:
                break
            start += batch_size

    def get_location(self, location_id: GlpiId) -> GetLocation:
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
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        return self._resource_get(
            f"{LOCATION_ENDPOINT}/{location_id}",
            GetLocation,
            failure_message=f"Failed to get location {location_id}",
        )

    def create_location(self, location: PostLocation) -> int:
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
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        GlpiProtocolError
            If the create response is missing the ``id`` field.
        """

        return self._resource_create(
            LOCATION_ENDPOINT,
            location,
            failure_message="Failed to create location",
            missing_message="GLPI location create response did not include an ID",
            log_message_factory=lambda new_id: f"GLPI API created location {new_id}",
        )

    def update_location(
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
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        self._resource_update(
            f"{LOCATION_ENDPOINT}/{location_id}",
            location,
            failure_message=f"Failed to update location {location_id}",
            log_message=f"GLPI API updated location {location_id}",
        )

    def delete_location(
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
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        self._resource_delete(
            f"{LOCATION_ENDPOINT}/{location_id}",
            failure_message=f"Failed to delete location {location_id}",
            log_message=f"GLPI API deleted location {location_id}",
            force=force,
            delete_model_cls=DeleteLocation,
        )


__all__ = ["LocationMixin"]
