from __future__ import annotations

from glpi_python_client.content.records.parsers.directory import _glpi_entity_record


def test_entity_record_normalizes_full_name_and_extra_payload() -> None:
    entity = _glpi_entity_record(
        {
            "id": 42,
            "name": "Novahe",
            "completename": "Root > Novahe",
            "comment": "Customer entity",
            "is_recursive": 1,
        }
    )

    assert entity.entity_id == "42"
    assert entity.name == "Novahe"
    assert entity.complete_name == "Root > Novahe"
    assert entity.comment == "Customer entity"
    assert entity.extra_payload == {"is_recursive": 1}
