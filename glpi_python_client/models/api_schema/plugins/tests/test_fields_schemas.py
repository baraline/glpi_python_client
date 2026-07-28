"""Smoke tests for the plugin-fields api_schema models."""

from __future__ import annotations

from glpi_python_client.models.api_schema.plugins import (
    GetPluginFieldsContainer,
    GetPluginFieldsField,
    GetPluginFieldsValueRow,
    PostPluginFieldsValueRow,
)


def test_get_container_full_payload() -> None:
    """``GetPluginFieldsContainer`` accepts every documented row field."""

    payload = {
        "id": 10,
        "name": "extrainfo",
        "label": "Extra information",
        "itemtypes": '["Ticket"]',
        "type": "tab",
        "subtype": None,
        "entities_id": 0,
        "is_recursive": True,
        "is_active": True,
        "links": [{"rel": "Entity", "href": "https://example/Entity/0"}],
    }
    container = GetPluginFieldsContainer.model_validate(payload)
    assert container.name == "extrainfo"
    # The undocumented ``links`` key flows through extra_payload.
    assert "links" in container.extra_payload


def test_get_field_full_payload() -> None:
    """``GetPluginFieldsField`` accepts every documented field declaration row."""

    payload = {
        "id": 11,
        "name": "extrainfofield",
        "label": "Extra information",
        "type": "richtext",
        "plugin_fields_containers_id": 10,
        "ranking": 1,
        "default_value": "",
        "is_active": True,
        "is_readonly": True,
        "mandatory": False,
        "multiple": False,
        "allowed_values": None,
    }
    field = GetPluginFieldsField.model_validate(payload)
    assert field.plugin_fields_containers_id == 10
    assert field.type == "richtext"


def test_value_row_dynamic_columns_in_extra_payload() -> None:
    """Dynamic field columns are captured by ``extra_payload``."""

    row = GetPluginFieldsValueRow.model_validate(
        {
            "id": 1,
            "items_id": 1234,
            "itemtype": "Ticket",
            "plugin_fields_containers_id": 10,
            "entities_id": 0,
            "extrainfofield": "<p>test</p>",
        }
    )
    assert row.items_id == 1234
    assert row.extra_payload["extrainfofield"] == "<p>test</p>"


def test_post_value_row_carries_dynamic_columns() -> None:
    """The POST body accepts dynamic field columns via ``extra_payload``."""

    body = PostPluginFieldsValueRow(
        items_id=1234,
        itemtype="Ticket",
        plugin_fields_containers_id=10,
        extra_payload={"extrainfofield": "<p>x</p>"},
    )
    assert body.extra_payload == {"extrainfofield": "<p>x</p>"}
