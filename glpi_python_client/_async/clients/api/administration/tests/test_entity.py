"""Unit tests for the ``Administration/Entity`` endpoint mixin.

The tests cover search, fetch, create, update, delete, and page-by-page
iteration for GLPI entities, using the shared transport recorders to stub
the four transport helpers without any HTTP plumbing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from glpi_python_client import PatchEntity, PostEntity
from glpi_python_client._async._testing import (
    FailingTransportRecorder,
    TransportRecorder,
)

# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


async def test_search_entities_skips_entity_header(client: Any) -> None:
    """``search_entities`` skips the GLPI-Entity header."""

    rec = TransportRecorder(get_payload=[{"id": 1, "name": "root"}])
    rec.install(client)
    entities = await client.search_entities("name==root", limit=None, start=0)
    assert entities[0].id == 1
    assert rec.calls[0]["skip_entity"] is True
    assert "limit" not in rec.calls[0]["params"]


async def test_get_entity_skips_entity_header(client: Any) -> None:
    """``get_entity`` also bypasses the entity header."""

    rec = TransportRecorder(get_payload={"id": 2, "name": "root"})
    rec.install(client)
    entity = await client.get_entity(2)
    assert entity.id == 2
    assert rec.calls[0]["endpoint"] == "Administration/Entity/2"
    assert rec.calls[0]["skip_entity"] is True


async def test_update_entity_patch(client: Any) -> None:
    """``update_entity`` patches the per-id endpoint."""

    rec = TransportRecorder()
    rec.install(client)
    await client.update_entity(2, PatchEntity(name="renamed"))
    assert rec.calls[0]["endpoint"] == "Administration/Entity/2"


async def test_delete_entity_with_force(client: Any) -> None:
    """``delete_entity(force=True)`` ships the force flag and skips entity."""

    rec = TransportRecorder()
    rec.install(client)
    await client.delete_entity(2, force=True)
    call = rec.calls[0]
    assert call["endpoint"] == "Administration/Entity/2"
    assert call["json"] == {"force": True}
    assert call["skip_entity"] is True


async def test_create_entity_id_returned(client: Any) -> None:
    """``create_entity`` returns the newly created identifier."""

    rec = TransportRecorder(post_payload={"id": 42})
    rec.install(client)
    entity_id = await client.create_entity(PostEntity(name="root"))
    assert entity_id == 42
    assert rec.calls[0]["endpoint"] == "Administration/Entity"
    assert rec.calls[0]["skip_entity"] is True


async def test_create_entity_skips_entity_header(client: Any) -> None:
    """Entity create requests bypass the GLPI-Entity header."""

    rec = TransportRecorder()
    rec.install(client)
    await client.create_entity(PostEntity(name="root"))
    call = rec.calls[0]
    assert call["endpoint"] == "Administration/Entity"
    assert call["skip_entity"] is True


# ---------------------------------------------------------------------------
# Generic error handling (this mixin's share of the shared failure suites)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.get_entity(1),
    ],
)
async def test_get_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every read helper raises on a non-success status."""

    FailingTransportRecorder(404).install(client)
    with pytest.raises(ValueError):
        await call(client)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.update_entity(1, PatchEntity(name="x")),
    ],
)
async def test_update_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every update helper raises on a non-success status."""

    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        await call(client)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.delete_entity(1, force=True),
    ],
)
async def test_delete_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every delete helper raises on a non-success status."""

    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        await call(client)


# ---------------------------------------------------------------------------
# iter_search_entities
# ---------------------------------------------------------------------------


async def test_iter_search_entities_single_page(client: Any) -> None:
    """A response shorter than batch_size yields one batch then stops."""

    call_count = 0

    async def fake_search(
        rsql_filter: str = "",
        *,
        limit: int | None = 50,
        start: int = 0,
    ) -> list[Any]:
        nonlocal call_count
        call_count += 1
        return [{"id": 1, "name": "root"}]

    client.search_entities = fake_search  # type: ignore[method-assign]
    batches = [b async for b in client.iter_search_entities("", batch_size=50)]
    assert call_count == 1
    assert len(batches) == 1


async def test_iter_search_entities_multi_page_stops_on_short_batch(
    client: Any,
) -> None:
    """Iteration stops after the first short entity batch."""

    responses = [
        [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}],
        [{"id": 3, "name": "c"}],
    ]
    call_count = 0

    async def fake_search(
        rsql_filter: str = "",
        *,
        limit: int | None = 50,
        start: int = 0,
    ) -> list[Any]:
        nonlocal call_count
        result = responses[min(call_count, len(responses) - 1)]
        call_count += 1
        return result

    client.search_entities = fake_search  # type: ignore[method-assign]
    batches = [batch async for batch in client.iter_search_entities("", batch_size=2)]
    assert call_count == 2
    assert sum(len(b) for b in batches) == 3
