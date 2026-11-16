"""GLPI ``ITILCategory`` schemas for the ``/Dropdowns/ITILCategory`` endpoints.

The field layout mirrors ``components.schemas.ITILCategory`` from the GLPI
OpenAPI contract. Read-only contract fields (``id``, ``completename``,
``level``) are excluded from request models.
"""

from __future__ import annotations

from datetime import datetime

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema._common import IdNameRef


class GetITILCategory(GlpiModel):
    """Response shape returned by ``GET /Dropdowns/ITILCategory`` endpoints.

    Mirrors ``components.schemas.ITILCategory``. No field carries a
    ``description`` in the OpenAPI contract; the parameter notes below
    reflect the field names, types and ``readOnly`` flags as advertised.

    Parameters
    ----------
    id : int | None, optional
        Native GLPI identifier (``readOnly``).
    name : str | None, optional
        Short display name of the category.
    completename : str | None, optional
        Full hierarchical path of the category (``readOnly``).
    level : int | None, optional
        Depth of the category in the hierarchy tree (``readOnly``).
    comment : str | None, optional
        Free-form comment associated with the category.
    entity : IdNameRef | None, optional
        Reference to the owning GLPI entity.
    is_recursive : bool | None, optional
        Whether the category is visible to child entities.
    parent : IdNameRef | None, optional
        Reference to the parent category in the hierarchy.
    user : IdNameRef | None, optional
        Reference to the user in charge of the category.
    group : IdNameRef | None, optional
        Reference to the group in charge of the category.
    code : str | None, optional
        Short code assigned to the category.
    is_helpdesk_visible : bool | None, optional
        Whether the category is visible in the simplified interface.
    ticket_incident_template : IdNameRef | None, optional
        Default ticket template for incidents.
    ticket_request_template : IdNameRef | None, optional
        Default ticket template for requests.
    change_template : IdNameRef | None, optional
        Default change template.
    problem_template : IdNameRef | None, optional
        Default problem template.
    is_incident_visible : bool | None, optional
        Whether the category can be used on incidents.
    is_request_visible : bool | None, optional
        Whether the category can be used on requests.
    is_change_visible : bool | None, optional
        Whether the category can be used on changes.
    is_problem_visible : bool | None, optional
        Whether the category can be used on problems.
    knowbase_category : IdNameRef | None, optional
        Reference to the linked knowledge base category.
    date_creation : datetime | None, optional
        Creation timestamp of the record (``format: date-time``).
    date_mod : datetime | None, optional
        Last modification timestamp of the record (``format: date-time``).
    """

    id: int | None = None
    name: str | None = None
    completename: str | None = None
    level: int | None = None
    comment: str | None = None
    entity: IdNameRef | None = None
    is_recursive: bool | None = None
    parent: IdNameRef | None = None
    user: IdNameRef | None = None
    group: IdNameRef | None = None
    code: str | None = None
    is_helpdesk_visible: bool | None = None
    ticket_incident_template: IdNameRef | None = None
    ticket_request_template: IdNameRef | None = None
    change_template: IdNameRef | None = None
    problem_template: IdNameRef | None = None
    is_incident_visible: bool | None = None
    is_request_visible: bool | None = None
    is_change_visible: bool | None = None
    is_problem_visible: bool | None = None
    knowbase_category: IdNameRef | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None


class PostITILCategory(GlpiModel):
    """Request body for ``POST /Dropdowns/ITILCategory``.

    Read-only contract fields (``id``, ``completename``, ``level``) are
    intentionally excluded because the server rejects them on input.

    Parameters
    ----------
    name : str | None, optional
        Short display name of the category.
    comment : str | None, optional
        Free-form comment associated with the category.
    entity : IdNameRef | None, optional
        Reference to the owning GLPI entity.
    is_recursive : bool | None, optional
        Whether the category is visible to child entities.
    parent : IdNameRef | None, optional
        Reference to the parent category in the hierarchy.
    user : IdNameRef | None, optional
        Reference to the user in charge of the category.
    group : IdNameRef | None, optional
        Reference to the group in charge of the category.
    code : str | None, optional
        Short code assigned to the category.
    is_helpdesk_visible : bool | None, optional
        Whether the category is visible in the simplified interface.
    ticket_incident_template : IdNameRef | None, optional
        Default ticket template for incidents.
    ticket_request_template : IdNameRef | None, optional
        Default ticket template for requests.
    change_template : IdNameRef | None, optional
        Default change template.
    problem_template : IdNameRef | None, optional
        Default problem template.
    is_incident_visible : bool | None, optional
        Whether the category can be used on incidents.
    is_request_visible : bool | None, optional
        Whether the category can be used on requests.
    is_change_visible : bool | None, optional
        Whether the category can be used on changes.
    is_problem_visible : bool | None, optional
        Whether the category can be used on problems.
    knowbase_category : IdNameRef | None, optional
        Reference to the linked knowledge base category.
    date_creation : datetime | None, optional
        Creation timestamp to set on the record (``format: date-time``).
    date_mod : datetime | None, optional
        Last modification timestamp to set on the record
        (``format: date-time``).
    """

    name: str | None = None
    comment: str | None = None
    entity: IdNameRef | None = None
    is_recursive: bool | None = None
    parent: IdNameRef | None = None
    user: IdNameRef | None = None
    group: IdNameRef | None = None
    code: str | None = None
    is_helpdesk_visible: bool | None = None
    ticket_incident_template: IdNameRef | None = None
    ticket_request_template: IdNameRef | None = None
    change_template: IdNameRef | None = None
    problem_template: IdNameRef | None = None
    is_incident_visible: bool | None = None
    is_request_visible: bool | None = None
    is_change_visible: bool | None = None
    is_problem_visible: bool | None = None
    knowbase_category: IdNameRef | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None


class PatchITILCategory(PostITILCategory):
    """Request body for ``PATCH /Dropdowns/ITILCategory/{id}``.

    The contract uses the same ``ITILCategory`` schema for create and
    partial-update bodies; ``PatchITILCategory`` is kept distinct so client
    mixins can express the intent of the operation explicitly.
    """


class DeleteITILCategory(GlpiModel):
    """Query parameters for ``DELETE /Dropdowns/ITILCategory/{id}``.

    Parameters
    ----------
    force : bool | None, optional
        When ``True``, permanently delete the category instead of moving
        the record to the GLPI trash. When ``False`` or :data:`None`,
        the server applies its default behaviour.
    """

    force: bool | None = None


__all__ = [
    "DeleteITILCategory",
    "GetITILCategory",
    "PatchITILCategory",
    "PostITILCategory",
]
