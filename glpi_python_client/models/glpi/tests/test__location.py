from __future__ import annotations

from glpi_python_client import GlpiLocation


def test_location_payload_preserves_raw_location_id() -> None:
    location = GlpiLocation(location_id="0012", name="Paris")

    payload = location.to_api_payload()

    assert payload["id"] == "0012"
    assert payload["name"] == "Paris"
