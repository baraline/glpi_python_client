"""Unit tests for the ``Management/Contract`` endpoint mixin.

The tests cover search, fetch, create, update, and delete for GLPI
contracts, and pin the two modelling decisions the contract forced: a
``date``-typed ``date_begin`` and an enum-typed ``renewal_type``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from glpi_python_client import (
    GetContract,
    GlpiContractRenewalType,
    PatchContract,
    PostContract,
)
from glpi_python_client._async._testing import TransportRecorder


async def test_search_contracts_passes_filter(client: Any) -> None:
    """``search_contracts`` forwards the RSQL filter through ``filter``."""

    rec = TransportRecorder(get_payload=[{"id": 1, "name": "Support 2026"}])
    rec.install(client)
    contracts = await client.search_contracts("name==Support 2026")
    assert contracts[0].id == 1
    assert rec.calls[0]["endpoint"] == "Management/Contract"
    assert rec.calls[0]["params"]["filter"] == "name==Support 2026"


async def test_search_contracts_forwards_sort(client: Any) -> None:
    """``sort`` reaches the server when given, and is absent otherwise."""

    rec = TransportRecorder(get_payload=[])
    rec.install(client)
    await client.search_contracts(sort="date_begin:desc")
    assert rec.calls[0]["params"]["sort"] == "date_begin:desc"

    rec2 = TransportRecorder(get_payload=[])
    rec2.install(client)
    await client.search_contracts()
    assert "sort" not in rec2.calls[0]["params"]


async def test_iter_search_contracts_stops_on_short_page(client: Any) -> None:
    """Pagination stops once the server returns fewer rows than requested."""

    rec = TransportRecorder(get_payload=[{"id": 1}])
    rec.install(client)
    pages = [page async for page in client.iter_search_contracts(batch_size=2)]
    assert len(pages) == 1
    assert len(pages[0]) == 1
    assert len(rec.calls) == 1
    assert rec.calls[0]["params"] == {"limit": 2, "start": 0}


async def test_iter_search_contracts_yields_every_page(client: Any) -> None:
    """The generator advances ``start`` until a short page ends the walk.

    ``TransportRecorder`` replays one payload forever, so it cannot drive a
    multi-page walk. Replace ``search_contracts`` itself, as
    ``test_location.py`` does. The stub is a named function rather than a
    lambda: this module's twin is generated from it by a token rewriter,
    which can transform a ``def`` but cannot build one out of a lambda.
    """

    pages = [[GetContract(id=i) for i in range(3)], [GetContract(id=99)]]
    starts: list[int] = []

    async def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        sort: str | None = None,
    ) -> list[GetContract]:
        starts.append(start)
        index = start // limit
        return pages[index] if index < len(pages) else []

    client.search_contracts = fake_search  # type: ignore[method-assign]

    batches = [
        batch async for batch in client.iter_search_contracts("name==x", batch_size=3)
    ]

    assert starts == [0, 3]
    assert [len(b) for b in batches] == [3, 1]


async def test_get_contract_endpoint(client: Any) -> None:
    """``get_contract`` hits the per-id endpoint."""

    rec = TransportRecorder(get_payload={"id": 9, "name": "Support"})
    rec.install(client)
    contract = await client.get_contract(9)
    assert contract.id == 9
    assert rec.calls[0]["endpoint"] == "Management/Contract/9"


async def test_create_contract_returns_new_id(client: Any) -> None:
    """``create_contract`` posts the body and returns the server id."""

    rec = TransportRecorder(post_payload={"id": 77})
    rec.install(client)
    new_id = await client.create_contract(PostContract(name="Support"))
    assert new_id == 77
    assert rec.calls[0]["endpoint"] == "Management/Contract"


async def test_update_contract(client: Any) -> None:
    """``update_contract`` patches the per-id endpoint."""

    rec = TransportRecorder()
    rec.install(client)
    await client.update_contract(9, PatchContract(name="Support 2027"))
    assert rec.calls[0]["endpoint"] == "Management/Contract/9"


async def test_delete_contract_with_force(client: Any) -> None:
    """``delete_contract(force=True)`` ships the force flag."""

    rec = TransportRecorder()
    rec.install(client)
    await client.delete_contract(9, force=True)
    assert rec.calls[0]["json"]["force"] is True


async def test_date_begin_is_a_plain_date_not_a_datetime(client: Any) -> None:
    """``date_begin`` parses to ``date``.

    The contract declares ``format: date``. Modelling it as ``datetime``
    would make an aware value eligible for the server-clock conversion in
    ``models/_base.py``, which could roll the start date to the previous
    or next day.
    """

    contract = GetContract.model_validate({"id": 1, "date_begin": "2026-01-15"})
    assert contract.date_begin == date(2026, 1, 15)
    assert not isinstance(contract.date_begin, datetime)


async def test_date_begin_survives_a_write_unshifted(client: Any) -> None:
    """A ``date`` is serialised as-is, with no timezone conversion."""

    rec = TransportRecorder()
    rec.install(client)
    await client.update_contract(9, PatchContract(date_begin=date(2026, 1, 15)))
    assert rec.calls[0]["json"]["date_begin"] == "2026-01-15"


async def test_renewal_type_round_trips_as_an_enum(client: Any) -> None:
    """``renewal_type`` parses into ``GlpiContractRenewalType``."""

    contract = GetContract.model_validate({"id": 1, "renewal_type": 1})
    assert contract.renewal_type is GlpiContractRenewalType.TACIT


async def test_renewal_type_serialises_as_its_integer(client: Any) -> None:
    """The enum is numeric on the wire, as GLPI expects."""

    rec = TransportRecorder()
    rec.install(client)
    await client.update_contract(
        9, PatchContract(renewal_type=GlpiContractRenewalType.EXPLICIT)
    )
    assert rec.calls[0]["json"]["renewal_type"] == 2


async def test_costs_is_read_only_on_the_client_side() -> None:
    """``costs`` is returned but never written; cost lines have own endpoints."""

    assert "costs" in GetContract.model_fields
    assert "costs" not in PostContract.model_fields
    assert "costs" not in PatchContract.model_fields


async def test_post_contract_excludes_readonly_id() -> None:
    """``PostContract`` has no ``id``; the server assigns it."""

    assert "id" not in PostContract.model_fields
