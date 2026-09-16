"""Unit tests for the ``Dropdowns/ContractType`` endpoint mixin.

The tests cover search, fetch, create, update, and delete for GLPI
contract types, using the shared transport recorders to stub the four
transport helpers without any HTTP plumbing.
"""

from __future__ import annotations

from typing import Any

from glpi_python_client import PatchContractType, PostContractType
from glpi_python_client._async._testing import TransportRecorder


async def test_search_contract_types_passes_filter(client: Any) -> None:
    """``search_contract_types`` forwards the RSQL filter through ``filter``."""

    rec = TransportRecorder(get_payload=[{"id": 1, "name": "Maintenance"}])
    rec.install(client)
    types = await client.search_contract_types("name==Maintenance")
    assert types[0].id == 1
    assert rec.calls[0]["endpoint"] == "Dropdowns/ContractType"
    assert rec.calls[0]["params"]["filter"] == "name==Maintenance"


async def test_search_contract_types_omits_empty_filter(client: Any) -> None:
    """An empty filter is not sent, so the server lists everything visible."""

    rec = TransportRecorder(get_payload=[])
    rec.install(client)
    await client.search_contract_types()
    assert "filter" not in rec.calls[0]["params"]


async def test_iter_search_contract_types_stops_on_short_page(client: Any) -> None:
    """Pagination stops once the server returns fewer rows than requested."""

    rec = TransportRecorder(get_payload=[{"id": 1}])
    rec.install(client)
    pages = [page async for page in client.iter_search_contract_types(batch_size=2)]
    assert len(pages) == 1
    assert len(pages[0]) == 1
    assert len(rec.calls) == 1
    assert rec.calls[0]["params"] == {"limit": 2, "start": 0}


async def test_get_contract_type_endpoint(client: Any) -> None:
    """``get_contract_type`` hits the per-id endpoint."""

    rec = TransportRecorder(get_payload={"id": 9, "name": "Lease"})
    rec.install(client)
    contract_type = await client.get_contract_type(9)
    assert contract_type.id == 9
    assert rec.calls[0]["endpoint"] == "Dropdowns/ContractType/9"


async def test_create_contract_type_returns_new_id(client: Any) -> None:
    """``create_contract_type`` posts the body and returns the server id."""

    rec = TransportRecorder(post_payload={"id": 42})
    rec.install(client)
    new_id = await client.create_contract_type(PostContractType(name="Lease"))
    assert new_id == 42
    assert rec.calls[0]["endpoint"] == "Dropdowns/ContractType"
    assert rec.calls[0]["json"]["name"] == "Lease"


async def test_update_contract_type(client: Any) -> None:
    """``update_contract_type`` patches the per-id endpoint."""

    rec = TransportRecorder()
    rec.install(client)
    await client.update_contract_type(9, PatchContractType(name="Lease 2"))
    assert rec.calls[0]["endpoint"] == "Dropdowns/ContractType/9"
    assert rec.calls[0]["json"]["name"] == "Lease 2"


async def test_delete_contract_type_with_force(client: Any) -> None:
    """``delete_contract_type(force=True)`` ships the force flag."""

    rec = TransportRecorder()
    rec.install(client)
    await client.delete_contract_type(9, force=True)
    assert rec.calls[0]["endpoint"] == "Dropdowns/ContractType/9"
    assert rec.calls[0]["json"]["force"] is True


async def test_post_contract_type_excludes_readonly_id() -> None:
    """``PostContractType`` has no ``id``; the server assigns it."""

    assert "id" not in PostContractType.model_fields
