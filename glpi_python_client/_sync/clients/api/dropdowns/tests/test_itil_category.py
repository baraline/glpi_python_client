"""Unit tests for the ``Dropdowns/ITILCategory`` endpoint mixin."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from glpi_python_client import PatchITILCategory, PostITILCategory
from glpi_python_client._sync._testing import (
    FailingTransportRecorder,
    TransportRecorder,
)
from glpi_python_client.models.api_schema._common import IdNameRef
from glpi_python_client.models.api_schema.dropdowns import GetITILCategory


def test_search_itil_categories_passes_filter_and_paging(client: Any) -> None:
    """``search_itil_categories`` forwards filter, limit and start."""

    rec = TransportRecorder(get_payload=[{"id": 4, "name": "Network"}])
    rec.install(client)
    categories = client.search_itil_categories("name==x", limit=10, start=5)
    assert categories[0].id == 4
    call = rec.calls[0]
    assert call["endpoint"] == "Dropdowns/ITILCategory"
    assert call["params"] == {"limit": 10, "start": 5, "filter": "name==x"}
    assert call["skip_entity"] is False


def test_search_itil_categories_without_filter_sends_no_filter(
    client: Any,
) -> None:
    """With no filter the ``filter`` query parameter is omitted entirely."""

    rec = TransportRecorder(get_payload=[])
    rec.install(client)
    client.search_itil_categories()
    assert rec.calls[0]["params"] == {"limit": 50, "start": 0}
    assert "filter" not in rec.calls[0]["params"]


def test_search_itil_categories_forwards_skip_entity(client: Any) -> None:
    """``skip_entity=True`` reaches the transport."""

    rec = TransportRecorder(get_payload=[])
    rec.install(client)
    client.search_itil_categories("name==x", skip_entity=True)
    assert rec.calls[0]["skip_entity"] is True


def test_get_itil_category_targets_per_id_endpoint(client: Any) -> None:
    """``get_itil_category`` reads the per-id endpoint."""

    rec = TransportRecorder(get_payload={"id": 9, "name": "Network"})
    rec.install(client)
    category = client.get_itil_category(9)
    assert category.id == 9
    assert rec.calls[0]["endpoint"] == "Dropdowns/ITILCategory/9"
    assert rec.calls[0]["skip_entity"] is False


def test_get_itil_category_forwards_skip_entity(client: Any) -> None:
    """``skip_entity=True`` reaches the transport on a fetch."""

    rec = TransportRecorder(get_payload={"id": 9, "name": "Network"})
    rec.install(client)
    client.get_itil_category(9, skip_entity=True)
    assert rec.calls[0]["skip_entity"] is True


def test_create_itil_category_returns_new_id(client: Any) -> None:
    """``create_itil_category`` returns the identifier the server assigned."""

    rec = TransportRecorder(post_payload={"id": 42})
    rec.install(client)
    new_id = client.create_itil_category(PostITILCategory(name="Network"))
    assert new_id == 42
    assert rec.calls[0]["endpoint"] == "Dropdowns/ITILCategory"


def test_create_itil_category_sends_body_with_entity_and_parent(
    client: Any,
) -> None:
    """The body carries entity, parent and the visibility flags."""

    rec = TransportRecorder(post_payload={"id": 42})
    rec.install(client)
    client.create_itil_category(
        PostITILCategory(
            name="Network",
            entity=IdNameRef(id=7),
            parent=IdNameRef(id=3),
            is_recursive=True,
            is_incident_visible=True,
            is_request_visible=False,
        )
    )
    body = rec.calls[0]["json"]
    assert body["entity"]["id"] == 7
    assert body["parent"]["id"] == 3
    assert body["is_recursive"] is True
    assert body["is_incident_visible"] is True
    assert body["is_request_visible"] is False
    assert body["name"] == "Network"


def test_update_itil_category_sends_patch(client: Any) -> None:
    """``update_itil_category`` patches the per-id endpoint."""

    rec = TransportRecorder()
    rec.install(client)
    client.update_itil_category(9, PatchITILCategory(name="renamed"))
    assert rec.calls[0]["method"] == "PATCH"
    assert rec.calls[0]["endpoint"] == "Dropdowns/ITILCategory/9"
    assert rec.calls[0]["json"] == {"name": "renamed"}


def test_delete_itil_category_with_force(client: Any) -> None:
    """``delete_itil_category(force=True)`` ships the force flag."""

    rec = TransportRecorder()
    rec.install(client)
    client.delete_itil_category(9, force=True)
    call = rec.calls[0]
    assert call["method"] == "DELETE"
    assert call["endpoint"] == "Dropdowns/ITILCategory/9"
    assert call["json"] == {"force": True}


def test_delete_itil_category_without_force(client: Any) -> None:
    """Without ``force`` the body carries no force flag."""

    rec = TransportRecorder()
    rec.install(client)
    client.delete_itil_category(9)
    call = rec.calls[0]
    assert call["method"] == "DELETE"
    assert call["endpoint"] == "Dropdowns/ITILCategory/9"
    assert not call["json"]


def _read(client: Any) -> Any:
    return client.get_itil_category(1)


def _create(client: Any) -> Any:
    return client.create_itil_category(PostITILCategory(name="x"))


def _update(client: Any) -> Any:
    return client.update_itil_category(1, PatchITILCategory(name="x"))


def _delete(client: Any) -> Any:
    return client.delete_itil_category(1, force=True)


@pytest.mark.parametrize("call", [_read])
def test_read_helpers_raise_on_failure(
    client: Any, call: Callable[[Any], Awaitable[Any]]
) -> None:
    """Every read helper raises on a non-success status."""

    FailingTransportRecorder(404).install(client)
    with pytest.raises(ValueError):
        call(client)


@pytest.mark.parametrize("call", [_create])
def test_create_helpers_raise_on_failure(
    client: Any, call: Callable[[Any], Awaitable[Any]]
) -> None:
    """Every create helper raises on a non-success status."""

    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        call(client)


@pytest.mark.parametrize("call", [_update])
def test_update_helpers_raise_on_failure(
    client: Any, call: Callable[[Any], Awaitable[Any]]
) -> None:
    """Every update helper raises on a non-success status."""

    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        call(client)


@pytest.mark.parametrize("call", [_delete])
def test_delete_helpers_raise_on_failure(
    client: Any, call: Callable[[Any], Awaitable[Any]]
) -> None:
    """Every delete helper raises on a non-success status."""

    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        call(client)


def test_iter_search_itil_categories_yields_every_page(client: Any) -> None:
    """The generator advances ``start`` and forwards ``skip_entity``."""

    pages = [[GetITILCategory(id=i) for i in range(3)], [GetITILCategory(id=99)]]
    starts: list[int] = []
    skips: list[bool] = []

    def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        skip_entity: bool = False,
    ) -> list[GetITILCategory]:
        starts.append(start)
        assert len(starts) < 10, "the walk did not stop"
        skips.append(skip_entity)
        index = start // limit
        return pages[index] if index < len(pages) else []

    client.search_itil_categories = fake_search

    batches = [
        batch
        for batch in client.iter_search_itil_categories(
            "name==x", batch_size=3, skip_entity=True
        )
    ]

    assert starts == [0, 3]
    assert skips == [True, True]
    assert [len(b) for b in batches] == [3, 1]


def test_iter_search_itil_categories_stops_on_a_single_short_page(
    client: Any,
) -> None:
    """One short page is the last page; no second request is made."""

    starts: list[int] = []

    def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        skip_entity: bool = False,
    ) -> list[GetITILCategory]:
        starts.append(start)
        assert len(starts) < 10, "the walk did not stop"
        return [GetITILCategory(id=1)]

    client.search_itil_categories = fake_search

    batches = [batch for batch in client.iter_search_itil_categories()]

    assert starts == [0]
    assert len(batches) == 1


def test_iter_search_itil_categories_yields_nothing_when_empty(
    client: Any,
) -> None:
    """An empty first page yields no batch at all."""

    starts: list[int] = []

    def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        skip_entity: bool = False,
    ) -> list[GetITILCategory]:
        starts.append(start)
        assert len(starts) < 10, "the walk did not stop"
        return []

    client.search_itil_categories = fake_search

    assert [batch for batch in client.iter_search_itil_categories()] == []
