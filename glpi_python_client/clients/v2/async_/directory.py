"""Asynchronous user and location lookup operations for GLPI v2 clients.

This module contains the directory-style async search helpers used to query
users and locations through the GLPI high-level API.
"""

from __future__ import annotations

from glpi_python_client.clients.v2.common.constants import (
    LOCATION_ENDPOINT,
    USER_ENDPOINT,
)
from glpi_python_client.clients.v2.common.filters import rsql_contains_filter
from glpi_python_client.clients.v2.common.response_payloads import list_payload_records
from glpi_python_client.content.records.core.scalars import _optional_text
from glpi_python_client.content.records.parsers.directory import (
    _glpi_location_record,
    _glpi_user_record,
)
from glpi_python_client.models import GlpiLocation, GlpiUser

from .transport import AsyncTransportMixin


class AsyncDirectoryMixin(AsyncTransportMixin):
    """Asynchronous GLPI user and location lookup helpers.

    The methods in this mixin return typed directory models while awaiting the
    async transport helpers for remote execution.
    """

    async def search_users(
        self,
        rsql_filter: str = "",
        *,
        limit: int = 1,
        start: int = 0,
        skip_entity: bool = False,
    ) -> list[GlpiUser]:
        """Search GLPI users with an optional raw RSQL filter.

        The async helper preserves the same filtering and empty-result behavior
        as the synchronous implementation while awaiting the remote request.
        """

        params: dict[str, object] = {"limit": limit, "start": start}
        if rsql_filter:
            params["filter"] = rsql_filter
        response = await self._get_request(
            USER_ENDPOINT, params=params, skip_entity=skip_entity
        )
        if response.status_code not in (200, 206):
            return []
        return list_payload_records(
            response.json(),
            record_factory=lambda user: (
                _glpi_user_record(user)
                if _optional_text(user.get("id")) is not None
                else None
            ),
        )

    async def search_locations(self, name: str) -> list[GlpiLocation]:
        """Search GLPI locations by name.

        Blank names are rejected locally by returning an empty list, and remote
        non-success statuses are normalized to empty results.
        """

        location_filter = rsql_contains_filter("name", name)
        if location_filter is None:
            return []

        response = await self._get_request(
            LOCATION_ENDPOINT,
            params={"filter": location_filter},
        )
        if response.status_code not in (200, 206):
            return []
        return list_payload_records(
            response.json(),
            record_factory=lambda location: (
                _glpi_location_record(location)
                if _optional_text(location.get("id")) is not None
                and _optional_text(location.get("name")) is not None
                else None
            ),
        )
