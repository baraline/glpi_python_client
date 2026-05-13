"""GLPI nested reference parsing helpers.

These helpers normalize the mixed scalar-or-mapping reference fields that GLPI
uses for related objects such as users, entities, and categories.
"""

from __future__ import annotations

from typing import Any

from glpi_python_client.models import GlpiUser

from .scalars import _optional_int, _optional_text


def _glpi_id_value(value: Any) -> Any:
    """Return the ``id`` field from one GLPI mapping payload.

    Non-mapping values return ``None`` so callers can safely probe optional
    nested references without type checks at every call site.
    """

    if isinstance(value, dict):
        return value.get("id")
    return None


def _glpi_reference(value: Any) -> dict[str, object] | int | str | None:
    """Normalize one GLPI reference field using the API field shape.

    Mapping values are reduced to the supported reference keys, while scalar
    values are preserved as integers when possible and text otherwise.
    """

    if isinstance(value, dict):
        reference = _reference_mapping(value)
        return reference or None
    integer_value = _optional_int(value)
    if integer_value is not None:
        return integer_value
    return _optional_text(value)


def _glpi_id_reference(value: Any) -> dict[str, object] | int | None:
    """Normalize one GLPI reference whose scalar form must be an ID.

    This is used for fields that should never surface free text when GLPI sends
    a scalar reference representation.
    """

    if isinstance(value, dict):
        reference = _reference_mapping(value)
        return reference or None
    return _optional_int(value)


def _glpi_text_reference(value: Any) -> dict[str, object] | str | None:
    """Normalize one GLPI reference whose scalar form is textual.

    Mapping payloads are preserved as reduced references, while scalar values
    are coerced to stripped text.
    """

    if isinstance(value, dict):
        reference = _reference_mapping(value)
        return reference or None
    return _optional_text(value)


def _glpi_ticket_user_payload(value: Any) -> GlpiUser | None:
    """Build a lightweight ``GlpiUser`` from one nested ticket field.

    Ticket payloads often embed partial user records. This helper keeps only the
    fields that are meaningful for the package's ticket models.
    """

    if not isinstance(value, dict):
        return None
    user_id = _optional_text(value.get("id"))
    name = _optional_text(value.get("name"))
    email = _optional_text(value.get("email"))
    if user_id is None and name is None and email is None:
        return None
    return GlpiUser(user_id=user_id, name=name, email=email)


def _reference_mapping(value: dict[str, Any]) -> dict[str, object]:
    """Return the supported GLPI reference fields from one nested payload.

    Only the small subset of keys used by the package's models is preserved so
    reference payloads stay predictable.
    """

    return {
        key: field_value
        for key, field_value in value.items()
        if key in {"id", "name", "completename"} and field_value is not None
    }
