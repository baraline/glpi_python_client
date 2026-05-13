"""Typed GLPI location model.

The location model is used both for parsed directory responses and for outgoing
location-creation payloads.
"""

from __future__ import annotations

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models._payload import (
    ApiPayloadMixin,
    drop_empty_payload_values,
)


class GlpiLocation(ApiPayloadMixin, GlpiModel):
    """GLPI location rich object.

    Parameters
    ----------
    location_id : str | None, optional
        Native GLPI location identifier.
    name : str | None, optional
        Location display name.
    entity_id : int | None, optional
        Owning GLPI entity.
    """

    location_id: str | None = None
    name: str | None = None
    entity_id: int | None = None

    def _build_api_payload(self) -> dict[str, object]:
        """Return the raw GLPI location-create request body.

        Returns
        -------
        dict[str, object]
            Raw GLPI location-create request body.

        """

        location_id = self.location_id

        return drop_empty_payload_values(
            {
                "id": location_id,
                "name": self.name,
                "entity": {"id": self.entity_id}
                if self.entity_id is not None
                else None,
            }
        )
