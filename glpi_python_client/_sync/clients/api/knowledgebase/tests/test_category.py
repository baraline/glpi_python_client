"""Recorder-based unit tests for ``KBCategoryMixin``."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from glpi_python_client import PatchKBCategory, PostKBCategory
from glpi_python_client._sync._testing import FailingTransportRecorder
from glpi_python_client.testing.utils import FakeResponse


class _Recorder:
    """Transport recorder returning canned FakeResponse objects."""

    def __init__(self, *, get_payload: Any = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._get_payload = get_payload if get_payload is not None else []

    def install(self, client: Any) -> None:
        def _get(
            endpoint: str,
            params: dict[str, Any] | None = None,
            skip_entity: bool = False,
        ) -> FakeResponse:
            self.calls.append(
                {
                    "method": "GET",
                    "endpoint": endpoint,
                    "params": params,
                    "skip_entity": skip_entity,
                }
            )
            return FakeResponse(status_code=200, payload=self._get_payload)

        def _post(
            endpoint: str,
            json_body: dict[str, Any] | None = None,
            skip_entity: bool = False,
        ) -> FakeResponse:
            self.calls.append(
                {"method": "POST", "endpoint": endpoint, "json": json_body}
            )
            return FakeResponse(status_code=201, payload={"id": 55})

        def _patch(
            endpoint: str, json_body: dict[str, Any] | None = None
        ) -> FakeResponse:
            self.calls.append(
                {"method": "PATCH", "endpoint": endpoint, "json": json_body}
            )
            return FakeResponse(status_code=204, payload={})

        def _delete(
            endpoint: str,
            json_body: dict[str, Any] | None = None,
            skip_entity: bool = False,
        ) -> FakeResponse:
            self.calls.append(
                {"method": "DELETE", "endpoint": endpoint, "json": json_body}
            )
            return FakeResponse(status_code=204, payload={})

        client._get_request = _get  # type: ignore[method-assign]
        client._post_request = _post  # type: ignore[method-assign]
        client._update_request = _patch  # type: ignore[method-assign]
        client._delete_request = _delete  # type: ignore[method-assign]


def test_search_kb_categories_forwards_filter_and_language(client: Any) -> None:
    rec = _Recorder(get_payload=[{"id": 1, "name": "Network"}])
    rec.install(client)
    result = client.search_kb_categories(
        "name==Network", limit=5, start=2, sort="name:asc", language="fr_FR"
    )
    assert result[0].id == 1
    call = rec.calls[0]
    assert call["endpoint"] == "Knowledgebase/Category"
    assert call["params"]["filter"] == "name==Network"
    assert call["params"]["limit"] == 5
    assert call["params"]["start"] == 2
    assert call["params"]["sort"] == "name:asc"
    assert call["params"]["language"] == "fr_FR"


def test_get_kb_category_targets_per_id_endpoint(client: Any) -> None:
    rec = _Recorder(get_payload={"id": 9, "name": "Network"})
    rec.install(client)
    category = client.get_kb_category(9)
    assert category.id == 9
    assert rec.calls[0]["endpoint"] == "Knowledgebase/Category/9"


def test_create_kb_category_returns_new_id(client: Any) -> None:
    rec = _Recorder()
    rec.install(client)
    new_id = client.create_kb_category(PostKBCategory(name="Network"))
    assert new_id == 55
    call = rec.calls[0]
    assert call["method"] == "POST"
    assert call["endpoint"] == "Knowledgebase/Category"
    assert call["json"] == {"name": "Network"}


def test_update_kb_category_sends_patch(client: Any) -> None:
    rec = _Recorder()
    rec.install(client)
    client.update_kb_category(9, PatchKBCategory(comment="moved"))
    call = rec.calls[0]
    assert call["method"] == "PATCH"
    assert call["endpoint"] == "Knowledgebase/Category/9"
    assert call["json"] == {"comment": "moved"}


def test_delete_kb_category_with_force(client: Any) -> None:
    rec = _Recorder()
    rec.install(client)
    client.delete_kb_category(9, force=True)
    call = rec.calls[0]
    assert call["method"] == "DELETE"
    assert call["endpoint"] == "Knowledgebase/Category/9"
    assert call["json"] == {"force": True}


# ---------------------------------------------------------------------------
# Generic error handling (this mixin's share of the shared failure suites)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.get_kb_category(1),
    ],
)
def test_read_helpers_raise_on_failure(
    client: Any, call: Callable[[Any], Any]
) -> None:
    FailingTransportRecorder(404).install(client)
    with pytest.raises(ValueError):
        call(client)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.create_kb_category(PostKBCategory(name="x")),
    ],
)
def test_create_helpers_raise_on_failure(
    client: Any, call: Callable[[Any], Any]
) -> None:
    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        call(client)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.update_kb_category(1, PatchKBCategory(name="x")),
    ],
)
def test_update_helpers_raise_on_failure(
    client: Any, call: Callable[[Any], Any]
) -> None:
    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        call(client)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.delete_kb_category(1, force=True),
    ],
)
def test_delete_helpers_raise_on_failure(
    client: Any, call: Callable[[Any], Any]
) -> None:
    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        call(client)


def test_iter_search_kb_categories_yields_every_page(client: Any) -> None:
    """The generator advances ``start`` until a short page ends the walk."""

    from glpi_python_client.models.api_schema.knowledgebase import GetKBCategory

    pages = [[GetKBCategory(id=i) for i in range(3)], [GetKBCategory(id=99)]]
    starts: list[int] = []
    forwarded: dict[str, Any] = {}

    def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        sort: str | None = None,
        language: str | None = None,
    ) -> list[GetKBCategory]:
        starts.append(start)
        forwarded["language"] = language
        index = start // limit
        return pages[index] if index < len(pages) else []

    client.search_kb_categories = fake_search  # type: ignore[method-assign]

    batches = [
        batch
        for batch in client.iter_search_kb_categories(
            "name==x", batch_size=3, language="fr_FR"
        )
    ]

    assert starts == [0, 3]
    assert [len(b) for b in batches] == [3, 1]
    assert forwarded["language"] == "fr_FR"


def test_iter_search_kb_categories_stops_on_a_single_short_page(
    client: Any,
) -> None:
    """One short page is the last page; no second request is made."""

    from glpi_python_client.models.api_schema.knowledgebase import GetKBCategory

    starts: list[int] = []

    def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        sort: str | None = None,
        language: str | None = None,
    ) -> list[GetKBCategory]:
        starts.append(start)
        return [GetKBCategory(id=1)]

    client.search_kb_categories = fake_search  # type: ignore[method-assign]

    batches = [batch for batch in client.iter_search_kb_categories(batch_size=50)]

    assert starts == [0]
    assert len(batches) == 1


def test_iter_search_kb_categories_yields_nothing_when_empty(client: Any) -> None:
    """An empty first page yields no batch at all rather than one empty list."""

    from glpi_python_client.models.api_schema.knowledgebase import GetKBCategory

    def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        sort: str | None = None,
        language: str | None = None,
    ) -> list[GetKBCategory]:
        return []

    client.search_kb_categories = fake_search  # type: ignore[method-assign]

    assert [batch for batch in client.iter_search_kb_categories()] == []
