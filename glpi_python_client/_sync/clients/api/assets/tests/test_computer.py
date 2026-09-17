"""Unit tests for the ``Assets/Computer`` endpoint mixin.

The tests cover search, fetch, create, update, and delete for GLPI
computers, using the shared transport recorders to stub the four
transport helpers without any HTTP plumbing.
"""

from __future__ import annotations

from typing import Any

from glpi_python_client import (
    GetComputer,
    IdNameRef,
    PatchComputer,
    PatchContractItem,
    PostComputer,
    PostContractItem,
)
from glpi_python_client._sync._testing import TransportRecorder


def test_search_computers_passes_filter(client: Any) -> None:
    """``search_computers`` forwards the RSQL filter through ``filter``."""

    rec = TransportRecorder(get_payload=[{"id": 1, "name": "LAPTOP-01"}])
    rec.install(client)
    computers = client.search_computers("name==LAPTOP-01")
    assert computers[0].id == 1
    assert rec.calls[0]["endpoint"] == "Assets/Computer"
    assert rec.calls[0]["params"]["filter"] == "name==LAPTOP-01"


def test_search_computers_forwards_sort(client: Any) -> None:
    """``sort`` reaches the server when given, and is absent otherwise."""

    rec = TransportRecorder(get_payload=[])
    rec.install(client)
    client.search_computers(sort="date_mod:desc")
    assert rec.calls[0]["params"]["sort"] == "date_mod:desc"

    rec2 = TransportRecorder(get_payload=[])
    rec2.install(client)
    client.search_computers()
    assert "sort" not in rec2.calls[0]["params"]


def test_iter_search_computers_stops_on_short_page(client: Any) -> None:
    """Pagination stops once the server returns fewer rows than requested.

    The recorder answers every GET with the same payload, so a generator
    that did not stop on a short page would loop forever here rather than
    fail an assertion.
    """

    rec = TransportRecorder(get_payload=[{"id": 1}, {"id": 2}])
    rec.install(client)
    pages = [page for page in client.iter_search_computers(batch_size=3)]
    assert len(pages) == 1
    assert len(pages[0]) == 2
    assert len(rec.calls) == 1
    assert rec.calls[0]["params"] == {"limit": 3, "start": 0}


def test_iter_search_computers_yields_every_page(client: Any) -> None:
    """The generator advances ``start`` until a short page ends the walk.

    ``TransportRecorder`` replays one payload forever, so it cannot drive a
    multi-page walk. Replace ``search_computers`` itself, as
    ``test_location.py`` does. The stub is a named function rather than a
    lambda: this module's twin is generated from it by a token rewriter,
    which can transform a ``def`` but cannot build one out of a lambda.
    """

    pages = [[GetComputer(id=i) for i in range(3)], [GetComputer(id=99)]]
    starts: list[int] = []

    def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        sort: str | None = None,
    ) -> list[GetComputer]:
        starts.append(start)
        index = start // limit
        return pages[index] if index < len(pages) else []

    client.search_computers = fake_search  # type: ignore[method-assign]

    batches = [
        batch for batch in client.iter_search_computers("name==x", batch_size=3)
    ]

    assert starts == [0, 3]
    assert [len(b) for b in batches] == [3, 1]


def test_get_computer_endpoint(client: Any) -> None:
    """``get_computer`` hits the per-id endpoint."""

    rec = TransportRecorder(get_payload={"id": 9, "name": "LAPTOP-01"})
    rec.install(client)
    computer = client.get_computer(9)
    assert computer.id == 9
    assert rec.calls[0]["endpoint"] == "Assets/Computer/9"


def test_create_computer_returns_new_id(client: Any) -> None:
    """``create_computer`` posts the body and returns the server id."""

    rec = TransportRecorder(post_payload={"id": 31})
    rec.install(client)
    new_id = client.create_computer(PostComputer(name="LAPTOP-02"))
    assert new_id == 31
    assert rec.calls[0]["endpoint"] == "Assets/Computer"
    assert rec.calls[0]["json"]["name"] == "LAPTOP-02"


def test_update_computer(client: Any) -> None:
    """``update_computer`` patches the per-id endpoint."""

    rec = TransportRecorder()
    rec.install(client)
    client.update_computer(9, PatchComputer(serial="SN-123"))
    assert rec.calls[0]["endpoint"] == "Assets/Computer/9"
    assert rec.calls[0]["json"]["serial"] == "SN-123"


def test_delete_computer_with_force(client: Any) -> None:
    """``delete_computer(force=True)`` ships the force flag."""

    rec = TransportRecorder()
    rec.install(client)
    client.delete_computer(9, force=True)
    assert rec.calls[0]["json"]["force"] is True


def test_group_fields_parse_as_lists_of_references(client: Any) -> None:
    """``group`` and ``group_tech`` are arrays in the contract, not scalars."""

    computer = GetComputer.model_validate(
        {
            "id": 1,
            "group": [{"id": 4, "name": "Support"}],
            "group_tech": [{"id": 5, "name": "Techs"}],
        }
    )
    assert computer.group is not None
    assert computer.group[0].name == "Support"
    assert computer.group_tech is not None
    assert computer.group_tech[0].id == 5


def test_post_computer_excludes_every_readonly_field() -> None:
    """The four contract ``readOnly`` fields never reach a write body."""

    for field in ("id", "uuid", "last_inventory_update", "last_boot"):
        assert field not in PostComputer.model_fields, field
        assert field not in PatchComputer.model_fields, field


# ---------------------------------------------------------------------------
# Computer <-> contract links
# ---------------------------------------------------------------------------


def test_list_computer_contracts_endpoint(client: Any) -> None:
    """``list_computer_contracts`` hits the contract sub-resource."""

    rec = TransportRecorder(
        get_payload=[{"id": 2, "contract": {"id": 7, "name": "Support"}}]
    )
    rec.install(client)
    links = client.list_computer_contracts(9)
    assert links[0].contract is not None
    assert links[0].contract.name == "Support"
    assert rec.calls[0]["endpoint"] == "Assets/Computer/9/Contract"


def test_get_computer_contract_endpoint(client: Any) -> None:
    """``get_computer_contract`` hits the per-link endpoint."""

    rec = TransportRecorder(get_payload={"id": 2})
    rec.install(client)
    link = client.get_computer_contract(9, 2)
    assert link.id == 2
    assert rec.calls[0]["endpoint"] == "Assets/Computer/9/Contract/2"


def test_link_computer_contract_sets_itemtype_itself(client: Any) -> None:
    """The client fills ``itemtype`` and ``items_id``, not the caller.

    ``Contract_Item.itemtype`` is a free string in the contract, so a typo
    there is a silently wrong link. The mixin knows it is working on a
    computer and says so.
    """

    rec = TransportRecorder(post_payload={"id": 4})
    rec.install(client)
    new_id = client.link_computer_contract(
        9, PostContractItem(contract=IdNameRef(id=7))
    )
    assert new_id == 4
    assert rec.calls[0]["endpoint"] == "Assets/Computer/9/Contract"
    assert rec.calls[0]["json"]["itemtype"] == "Computer"
    assert rec.calls[0]["json"]["items_id"] == 9


def test_link_computer_contract_overrides_a_caller_itemtype(
    client: Any,
) -> None:
    """A caller-supplied itemtype cannot point the link at another type."""

    rec = TransportRecorder(post_payload={"id": 4})
    rec.install(client)
    client.link_computer_contract(
        9, PostContractItem(contract=IdNameRef(id=7), itemtype="Monitor", items_id=1)
    )
    assert rec.calls[0]["json"]["itemtype"] == "Computer"
    assert rec.calls[0]["json"]["items_id"] == 9


def test_update_computer_contract(client: Any) -> None:
    """``update_computer_contract`` patches the per-link endpoint."""

    rec = TransportRecorder()
    rec.install(client)
    client.update_computer_contract(
        9, 2, PatchContractItem(contract=IdNameRef(id=8))
    )
    assert rec.calls[0]["endpoint"] == "Assets/Computer/9/Contract/2"


def test_unlink_computer_contract_with_force(client: Any) -> None:
    """``unlink_computer_contract(force=True)`` ships the force flag."""

    rec = TransportRecorder()
    rec.install(client)
    client.unlink_computer_contract(9, 2, force=True)
    assert rec.calls[0]["endpoint"] == "Assets/Computer/9/Contract/2"
    assert rec.calls[0]["json"]["force"] is True
