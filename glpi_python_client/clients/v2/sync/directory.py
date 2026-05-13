"""Synchronous user and location lookup operations for GLPI v2 clients.

This module contains the directory-style search helpers used to query users and
locations through the GLPI high-level API.
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

from .transport import SyncTransportMixin


class SyncDirectoryMixin(SyncTransportMixin):
    """Synchronous GLPI user and location lookup helpers.

    The methods in this mixin return typed directory models and hide the
    filtering and payload-normalization details required by the GLPI API.
    """

    def search_users(
        self,
        rsql_filter: str = "",
        *,
        limit: int = 1,
        start: int = 0,
        skip_entity: bool = False,
    ) -> list[GlpiUser]:
        """Search GLPI users with an optional raw RSQL filter.

        The method returns only records that include a usable GLPI user ID and
        silently yields an empty list when the remote endpoint does not return a
        success status.
        """

        params: dict[str, object] = {"limit": limit, "start": start}
        if rsql_filter:
            params["filter"] = rsql_filter
        response = self._get_request(
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

    def search_locations(self, name: str) -> list[GlpiLocation]:
        """Search GLPI locations by name.

        Blank names are filtered out locally, and non-success API responses are
        normalized to an empty result list so callers can treat this as a lookup
        helper rather than a strict mutation-style operation.
        """

        location_filter = rsql_contains_filter("name", name)
        if location_filter is None:
            return []

        response = self._get_request(
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
