"""Unit tests for the GLPI ``Fields`` plugin client mixin."""

from __future__ import annotations

from typing import Any

import pytest

from glpi_python_client import GlpiClient, GlpiProtocolError, GlpiValidationError
from glpi_python_client._sync.clients.api.plugins._fields import (
    _container_targets_itemtype,
    _extract_row_id,
    _value_itemtype_for,
)
from glpi_python_client.models.api_schema.plugins import (
    GetPluginFieldsContainer,
)
from glpi_python_client.testing.utils import make_client


class _FakeV1:
    """Stand-in for :class:`GLPIV1Session` that records ``request_json`` calls."""

    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, object] | None = None,
        json_body: dict[str, object] | None = None,
        success_statuses: tuple[int, ...] = (200, 201, 204, 206),
        failure_message: str | None = None,
    ) -> object:
        self.calls.append(
            {
                "method": method,
                "path": path,
                "params": params,
                "json_body": json_body,
                "success_statuses": success_statuses,
                "failure_message": failure_message,
            }
        )
        if not self.responses:
            raise AssertionError(
                f"Unexpected v1 call: {method} {path} (no more queued responses)"
            )
        return self.responses.pop(0)


@pytest.fixture
def client() -> GlpiClient:
    """Return a client without any HTTP plumbing wired up."""

    return make_client()


def test_value_itemtype_naming() -> None:
    """The value itemtype is built from parent type + lowercase container."""

    assert (
        _value_itemtype_for("Ticket", "aidelarsolution")
        == "PluginFieldsTicketaidelarsolution"
    )
    # Mixed-case names get normalised to lowercase to match the v1 routes.
    assert (
        _value_itemtype_for("Ticket", "MyContainer") == "PluginFieldsTicketmycontainer"
    )


def test_container_targets_itemtype_parses_json_array() -> None:
    """The JSON-encoded ``itemtypes`` string is parsed for filtering."""

    container = GetPluginFieldsContainer(
        id=1, name="x", itemtypes='["Ticket","Computer"]'
    )
    assert _container_targets_itemtype(container, "Ticket")
    assert not _container_targets_itemtype(container, "Problem")


def test_container_targets_itemtype_substring_fallback() -> None:
    """A non-JSON ``itemtypes`` string falls back to a substring check."""

    container = GetPluginFieldsContainer(id=1, name="x", itemtypes="Ticket")
    assert _container_targets_itemtype(container, "Ticket")


def test_container_targets_itemtype_handles_empty() -> None:
    """Containers with no ``itemtypes`` value never match."""

    container = GetPluginFieldsContainer(id=1, name="x", itemtypes=None)
    assert not _container_targets_itemtype(container, "Ticket")


def test_extract_row_id_parses_plugin_response() -> None:
    """The plugin response shape ``[{"<id>": true, "message": ""}]`` is decoded."""

    assert _extract_row_id([{"42": True, "message": ""}]) == 42


def test_extract_row_id_rejects_unexpected_payload() -> None:
    """Unexpected payloads raise ``GlpiProtocolError``, also a ``ValueError``."""

    with pytest.raises(GlpiProtocolError) as excinfo:
        _extract_row_id([])
    assert isinstance(excinfo.value, ValueError)

    with pytest.raises(GlpiProtocolError) as excinfo:
        _extract_row_id([{"message": ""}])
    assert isinstance(excinfo.value, ValueError)

    with pytest.raises(GlpiProtocolError) as excinfo:
        _extract_row_id([42])
    assert isinstance(excinfo.value, ValueError)


def test_require_v1_raises_without_session(client: GlpiClient) -> None:
    """Every helper raises ``RuntimeError`` when the v1 session is missing."""

    assert client._v1 is None
    with pytest.raises(RuntimeError, match="v1 session"):
        client.list_plugin_fields_containers()


def test_list_plugin_fields_containers_filters_itemtype(client: GlpiClient) -> None:
    """Client-side filtering keeps only the containers attached to itemtype."""

    fake = _FakeV1(
        responses=[
            [
                {"id": 1, "name": "a", "itemtypes": '["Ticket"]'},
                {"id": 2, "name": "b", "itemtypes": '["Computer"]'},
                {"id": 3, "name": "c", "itemtypes": '["Ticket","Problem"]'},
            ]
        ]
    )
    client._v1 = fake  # type: ignore[assignment]
    result = client.list_plugin_fields_containers(itemtype="Ticket")
    assert [c.id for c in result] == [1, 3]
    assert fake.calls[0]["path"] == "PluginFieldsContainer"
    assert fake.calls[0]["params"] == {"range": "0-999"}


def test_list_plugin_fields_fields_filters_by_container(client: GlpiClient) -> None:
    """Field listing applies the optional container filter client-side."""

    fake = _FakeV1(
        responses=[
            [
                {"id": 1, "name": "a", "plugin_fields_containers_id": 10},
                {"id": 2, "name": "b", "plugin_fields_containers_id": 11},
            ]
        ]
    )
    client._v1 = fake  # type: ignore[assignment]
    result = client.list_plugin_fields_fields(container_id=10)
    assert [f.id for f in result] == [1]


def test_list_item_plugin_field_rows_hits_subresource(client: GlpiClient) -> None:
    """Per-item value rows go through ``/<Itemtype>/<id>/<value-itemtype>``."""

    fake = _FakeV1(
        responses=[
            [
                {
                    "id": 1,
                    "items_id": 62571,
                    "itemtype": "Ticket",
                    "plugin_fields_containers_id": 10,
                    "entities_id": 0,
                    "aidelarsolutionfield": "<p>test</p>",
                }
            ]
        ]
    )
    client._v1 = fake  # type: ignore[assignment]
    rows = client.list_item_plugin_field_rows("Ticket", 62571, "aidelarsolution")
    assert rows[0].extra_payload == {"aidelarsolutionfield": "<p>test</p>"}
    assert fake.calls[0]["path"] == "Ticket/62571/PluginFieldsTicketaidelarsolution"


def test_create_item_plugin_field_row_returns_new_id(client: GlpiClient) -> None:
    """Create POSTs ``{"input": ...}`` and returns the new row id."""

    fake = _FakeV1(responses=[[{"7": True, "message": ""}]])
    client._v1 = fake  # type: ignore[assignment]
    row_id = client.create_item_plugin_field_row(
        itemtype="Ticket",
        items_id=99,
        container_id=10,
        container_name="aidelarsolution",
        values={"aidelarsolutionfield": "<p>x</p>"},
        entities_id=3,
    )
    assert row_id == 7
    call = fake.calls[0]
    assert call["method"] == "POST"
    assert call["path"] == "PluginFieldsTicketaidelarsolution"
    assert call["json_body"] == {
        "input": {
            "items_id": 99,
            "itemtype": "Ticket",
            "plugin_fields_containers_id": 10,
            "aidelarsolutionfield": "<p>x</p>",
            "entities_id": 3,
        }
    }


def test_update_item_plugin_field_row_puts_partial_body(client: GlpiClient) -> None:
    """Update PUTs ``{"input": {"id": row_id, ...}}`` against the row endpoint."""

    fake = _FakeV1(responses=[[{"1": True, "message": ""}]])
    client._v1 = fake  # type: ignore[assignment]
    client.update_item_plugin_field_row(
        itemtype="Ticket",
        container_name="aidelarsolution",
        row_id=1,
        values={"aidelarsolutionfield": "<p>updated</p>"},
    )
    call = fake.calls[0]
    assert call["method"] == "PUT"
    assert call["path"] == "PluginFieldsTicketaidelarsolution/1"
    assert call["json_body"] == {
        "input": {"id": 1, "aidelarsolutionfield": "<p>updated</p>"}
    }


def test_get_ticket_custom_fields_aggregates_containers(client: GlpiClient) -> None:
    """The high-level helper aggregates per-container values into one mapping."""

    fake = _FakeV1(
        responses=[
            # 1. list_plugin_fields_containers(Ticket)
            [
                {"id": 10, "name": "aidelarsolution", "itemtypes": '["Ticket"]'},
                {"id": 2, "name": "sige", "itemtypes": '["Ticket"]'},
                {"id": 3, "name": "ignored", "itemtypes": '["Computer"]'},
            ],
            # 2. list_item_plugin_field_rows aidelarsolution
            [
                {
                    "id": 1,
                    "items_id": 62571,
                    "itemtype": "Ticket",
                    "plugin_fields_containers_id": 10,
                    "entities_id": 0,
                    "aidelarsolutionfield": "<p>test</p>",
                }
            ],
            # 3. list_item_plugin_field_rows sige -> no row yet
            [],
        ]
    )
    client._v1 = fake  # type: ignore[assignment]
    result = client.get_ticket_custom_fields(62571)
    assert result == {"aidelarsolution": {"aidelarsolutionfield": "<p>test</p>"}}


def test_set_ticket_custom_fields_updates_existing_row(client: GlpiClient) -> None:
    """When a row exists the high-level helper PATCHes it in place."""

    fake = _FakeV1(
        responses=[
            # list containers
            [
                {"id": 10, "name": "aidelarsolution", "itemtypes": '["Ticket"]'},
            ],
            # list fields for container 10
            [
                {
                    "id": 11,
                    "name": "aidelarsolutionfield",
                    "plugin_fields_containers_id": 10,
                }
            ],
            # list existing rows -> one row already present
            [
                {
                    "id": 1,
                    "items_id": 62571,
                    "itemtype": "Ticket",
                    "plugin_fields_containers_id": 10,
                }
            ],
            # PUT response
            [{"1": True, "message": ""}],
        ]
    )
    client._v1 = fake  # type: ignore[assignment]
    client.set_ticket_custom_fields(
        62571, {"aidelarsolution": {"aidelarsolutionfield": "<p>new</p>"}}
    )
    methods = [c["method"] for c in fake.calls]
    assert methods == ["GET", "GET", "GET", "PUT"]
    put = fake.calls[-1]
    assert put["json_body"] == {
        "input": {"id": 1, "aidelarsolutionfield": "<p>new</p>"}
    }


def test_set_ticket_custom_fields_creates_when_missing(client: GlpiClient) -> None:
    """When no row exists the high-level helper POSTs a new one."""

    fake = _FakeV1(
        responses=[
            [
                {"id": 10, "name": "aidelarsolution", "itemtypes": '["Ticket"]'},
            ],
            [
                {
                    "id": 11,
                    "name": "aidelarsolutionfield",
                    "plugin_fields_containers_id": 10,
                }
            ],
            [],  # no existing rows
            [{"99": True, "message": ""}],  # POST response
        ]
    )
    client._v1 = fake  # type: ignore[assignment]
    client.set_ticket_custom_fields(
        62571, {"aidelarsolution": {"aidelarsolutionfield": "<p>new</p>"}}
    )
    methods = [c["method"] for c in fake.calls]
    assert methods == ["GET", "GET", "GET", "POST"]
    post = fake.calls[-1]
    assert post["json_body"] == {
        "input": {
            "items_id": 62571,
            "itemtype": "Ticket",
            "plugin_fields_containers_id": 10,
            "aidelarsolutionfield": "<p>new</p>",
        }
    }


def test_set_ticket_custom_fields_rejects_unknown_container(client: GlpiClient) -> None:
    """A typo in the container name raises before any write.

    ``GlpiValidationError`` inherits ``ValueError`` so existing callers that
    catch the broader type keep working.
    """

    fake = _FakeV1(responses=[[{"id": 10, "name": "real", "itemtypes": '["Ticket"]'}]])
    client._v1 = fake  # type: ignore[assignment]
    with pytest.raises(
        GlpiValidationError, match="Unknown plugin-fields container"
    ) as excinfo:
        client.set_ticket_custom_fields(62571, {"typo": {"any": "value"}})
    # No mutation was sent.
    assert all(c["method"] == "GET" for c in fake.calls)
    assert isinstance(excinfo.value, ValueError)


def test_set_ticket_custom_fields_rejects_container_without_id(
    client: GlpiClient,
) -> None:
    """A matched container with no ``id`` raises before any write.

    The container came from the server's own
    :meth:`~glpi_python_client._sync.clients.api.plugins._fields.PluginFieldsMixin.list_plugin_fields_containers`
    response, so a missing ``id`` is a server-side contract violation, not
    a caller mistake: ``GlpiProtocolError``. It still inherits
    ``ValueError`` so existing callers that catch the broader type keep
    working.
    """

    fake = _FakeV1(responses=[[{"name": "aidelarsolution", "itemtypes": '["Ticket"]'}]])
    client._v1 = fake  # type: ignore[assignment]
    with pytest.raises(GlpiProtocolError, match="has no id") as excinfo:
        client.set_ticket_custom_fields(
            62571, {"aidelarsolution": {"aidelarsolutionfield": "value"}}
        )
    assert all(c["method"] == "GET" for c in fake.calls)
    assert isinstance(excinfo.value, ValueError)


def test_set_ticket_custom_fields_rejects_unknown_field(client: GlpiClient) -> None:
    """A typo in the field name raises before any write.

    ``GlpiValidationError`` inherits ``ValueError`` so existing callers that
    catch the broader type keep working.
    """

    fake = _FakeV1(
        responses=[
            [{"id": 10, "name": "aidelarsolution", "itemtypes": '["Ticket"]'}],
            [
                {
                    "id": 11,
                    "name": "aidelarsolutionfield",
                    "plugin_fields_containers_id": 10,
                }
            ],
        ]
    )
    client._v1 = fake  # type: ignore[assignment]
    with pytest.raises(GlpiValidationError, match="Unknown field") as excinfo:
        client.set_ticket_custom_fields(62571, {"aidelarsolution": {"typo": "value"}})
    assert isinstance(excinfo.value, ValueError)


def test_set_ticket_custom_fields_with_empty_mapping_is_noop(
    client: GlpiClient,
) -> None:
    """Passing an empty mapping performs no HTTP call."""

    fake = _FakeV1(responses=[])
    client._v1 = fake  # type: ignore[assignment]
    client.set_ticket_custom_fields(62571, {})
    assert fake.calls == []
