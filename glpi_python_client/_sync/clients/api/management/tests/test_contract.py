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
    GetContractCost,
    GlpiContractRenewalType,
    PatchContract,
    PatchContractCost,
    PostContract,
    PostContractCost,
)
from glpi_python_client._sync._testing import TransportRecorder


def test_search_contracts_passes_filter(client: Any) -> None:
    """``search_contracts`` forwards the RSQL filter through ``filter``."""

    rec = TransportRecorder(get_payload=[{"id": 1, "name": "Support 2026"}])
    rec.install(client)
    contracts = client.search_contracts("name==Support 2026")
    assert contracts[0].id == 1
    assert rec.calls[0]["endpoint"] == "Management/Contract"
    assert rec.calls[0]["params"]["filter"] == "name==Support 2026"


def test_search_contracts_forwards_sort(client: Any) -> None:
    """``sort`` reaches the server when given, and is absent otherwise."""

    rec = TransportRecorder(get_payload=[])
    rec.install(client)
    client.search_contracts(sort="date_begin:desc")
    assert rec.calls[0]["params"]["sort"] == "date_begin:desc"

    rec2 = TransportRecorder(get_payload=[])
    rec2.install(client)
    client.search_contracts()
    assert "sort" not in rec2.calls[0]["params"]


def test_iter_search_contracts_stops_on_short_page(client: Any) -> None:
    """Pagination stops once the server returns fewer rows than requested."""

    rec = TransportRecorder(get_payload=[{"id": 1}])
    rec.install(client)
    pages = [page for page in client.iter_search_contracts(batch_size=2)]
    assert len(pages) == 1
    assert len(pages[0]) == 1
    assert len(rec.calls) == 1
    assert rec.calls[0]["params"] == {"limit": 2, "start": 0}


def test_iter_search_contracts_yields_every_page(client: Any) -> None:
    """The generator advances ``start`` until a short page ends the walk.

    ``TransportRecorder`` replays one payload forever, so it cannot drive a
    multi-page walk. Replace ``search_contracts`` itself, as
    ``test_location.py`` does. The stub is a named function rather than a
    lambda: this module's twin is generated from it by a token rewriter,
    which can transform a ``def`` but cannot build one out of a lambda.
    """

    pages = [[GetContract(id=i) for i in range(3)], [GetContract(id=99)]]
    starts: list[int] = []
    sorts: list[str | None] = []

    def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        sort: str | None = None,
    ) -> list[GetContract]:
        starts.append(start)
        sorts.append(sort)
        index = start // limit
        return pages[index] if index < len(pages) else []

    client.search_contracts = fake_search  # type: ignore[method-assign]

    batches = [
        batch
        for batch in client.iter_search_contracts(
            "name==x", batch_size=3, sort="date_mod:desc"
        )
    ]

    assert starts == [0, 3]
    assert sorts == ["date_mod:desc", "date_mod:desc"]
    assert [len(b) for b in batches] == [3, 1]


def test_get_contract_endpoint(client: Any) -> None:
    """``get_contract`` hits the per-id endpoint."""

    rec = TransportRecorder(get_payload={"id": 9, "name": "Support"})
    rec.install(client)
    contract = client.get_contract(9)
    assert contract.id == 9
    assert rec.calls[0]["endpoint"] == "Management/Contract/9"


def test_create_contract_returns_new_id(client: Any) -> None:
    """``create_contract`` posts the body and returns the server id."""

    rec = TransportRecorder(post_payload={"id": 77})
    rec.install(client)
    new_id = client.create_contract(PostContract(name="Support"))
    assert new_id == 77
    assert rec.calls[0]["endpoint"] == "Management/Contract"


def test_update_contract(client: Any) -> None:
    """``update_contract`` patches the per-id endpoint."""

    rec = TransportRecorder()
    rec.install(client)
    client.update_contract(9, PatchContract(name="Support 2027"))
    assert rec.calls[0]["endpoint"] == "Management/Contract/9"


def test_delete_contract_with_force(client: Any) -> None:
    """``delete_contract(force=True)`` ships the force flag."""

    rec = TransportRecorder()
    rec.install(client)
    client.delete_contract(9, force=True)
    assert rec.calls[0]["json"]["force"] is True


def test_date_begin_is_a_plain_date_not_a_datetime(client: Any) -> None:
    """``date_begin`` parses to ``date``.

    The contract declares ``format: date``. Modelling it as ``datetime``
    would make an aware value eligible for the server-clock conversion in
    ``models/_base.py``, which could roll the start date to the previous
    or next day.
    """

    contract = GetContract.model_validate({"id": 1, "date_begin": "2026-01-15"})
    assert contract.date_begin == date(2026, 1, 15)
    assert not isinstance(contract.date_begin, datetime)


def test_date_begin_survives_a_write_unshifted(client: Any) -> None:
    """A ``date`` is serialised as-is, with no timezone conversion."""

    rec = TransportRecorder()
    rec.install(client)
    client.update_contract(9, PatchContract(date_begin=date(2026, 1, 15)))
    assert rec.calls[0]["json"]["date_begin"] == "2026-01-15"


def test_renewal_type_round_trips_as_an_enum(client: Any) -> None:
    """``renewal_type`` parses into ``GlpiContractRenewalType``."""

    contract = GetContract.model_validate({"id": 1, "renewal_type": 1})
    assert contract.renewal_type is GlpiContractRenewalType.TACIT


def test_renewal_type_serialises_as_its_integer(client: Any) -> None:
    """The enum is numeric on the wire, as GLPI expects."""

    rec = TransportRecorder()
    rec.install(client)
    client.update_contract(
        9, PatchContract(renewal_type=GlpiContractRenewalType.EXPLICIT)
    )
    assert rec.calls[0]["json"]["renewal_type"] == 2


def test_costs_is_read_only_on_the_client_side() -> None:
    """``costs`` is returned but never written; cost lines have own endpoints."""

    assert "costs" in GetContract.model_fields
    assert "costs" not in PostContract.model_fields
    assert "costs" not in PatchContract.model_fields


def test_post_contract_excludes_readonly_id() -> None:
    """``PostContract`` has no ``id``; the server assigns it."""

    assert "id" not in PostContract.model_fields


# ---------------------------------------------------------------------------
# Contract costs
# ---------------------------------------------------------------------------


def test_list_contract_costs_endpoint(client: Any) -> None:
    """``list_contract_costs`` hits the cost sub-resource of one contract."""

    rec = TransportRecorder(get_payload=[{"id": 3, "cost": 1200.0}])
    rec.install(client)
    costs = client.list_contract_costs(9)
    assert costs[0].cost == 1200.0
    assert rec.calls[0]["endpoint"] == "Management/Contract/9/Cost"


def test_get_contract_cost_endpoint(client: Any) -> None:
    """``get_contract_cost`` hits the per-cost endpoint."""

    rec = TransportRecorder(get_payload={"id": 3, "cost": 1200.0})
    rec.install(client)
    cost = client.get_contract_cost(9, 3)
    assert cost.id == 3
    assert rec.calls[0]["endpoint"] == "Management/Contract/9/Cost/3"


def test_create_contract_cost_returns_new_id(client: Any) -> None:
    """``create_contract_cost`` posts to the sub-resource and returns the id."""

    rec = TransportRecorder(post_payload={"id": 5})
    rec.install(client)
    new_id = client.create_contract_cost(
        9, PostContractCost(name="Year 1", cost=1200.0)
    )
    assert new_id == 5
    assert rec.calls[0]["endpoint"] == "Management/Contract/9/Cost"
    assert rec.calls[0]["json"]["cost"] == 1200.0


def test_update_contract_cost(client: Any) -> None:
    """``update_contract_cost`` patches the per-cost endpoint."""

    rec = TransportRecorder()
    rec.install(client)
    client.update_contract_cost(9, 3, PatchContractCost(cost=1500.0))
    assert rec.calls[0]["endpoint"] == "Management/Contract/9/Cost/3"


def test_delete_contract_cost_with_force(client: Any) -> None:
    """``delete_contract_cost(force=True)`` ships the force flag."""

    rec = TransportRecorder()
    rec.install(client)
    client.delete_contract_cost(9, 3, force=True)
    assert rec.calls[0]["endpoint"] == "Management/Contract/9/Cost/3"
    assert rec.calls[0]["json"]["force"] is True


def test_contract_cost_id_is_the_only_readonly_field() -> None:
    """``id`` is readable but never written; every other field is shared."""

    assert "id" in GetContractCost.model_fields
    assert "id" not in PostContractCost.model_fields
    assert "id" not in PatchContractCost.model_fields
