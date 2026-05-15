"""Shared helper schemas reused by GLPI API request and response models.

The GLPI OpenAPI contract represents foreign-key relationships as inline
``{"id": int, "name": str}`` objects. These small helper models keep the
shape consistent across every entity schema without depending on any specific
domain module.
"""

from __future__ import annotations

from glpi_python_client.models._base import GlpiModel


class IdRef(GlpiModel):
    """Foreign-key reference carrying only the GLPI identifier.

    The GLPI write endpoints accept foreign-key values as ``{"id": int}``
    objects. Use this helper to build outgoing request bodies that target a
    related GLPI item.

    Parameters
    ----------
    id : int | None, optional
        Native GLPI identifier of the referenced item.
    """

    id: int | None = None


class IdNameRef(GlpiModel):
    """Foreign-key reference carrying both id and read-only name.

    GLPI returns relationships as ``{"id": int, "name": str}`` payloads on
    most endpoints. The ``name`` value is server-managed and is preserved
    here purely for read-side convenience.

    Parameters
    ----------
    id : int | None, optional
        Native GLPI identifier of the referenced item.
    name : str | None, optional
        Server-provided display name of the referenced item.
    """

    id: int | None = None
    name: str | None = None


class IdNameCompletenameRef(GlpiModel):
    """Foreign-key reference carrying id, name, and completename.

    A few GLPI relationships, such as ``Ticket.entity``, surface a third
    ``completename`` slot that holds the dotted hierarchical name.

    Parameters
    ----------
    id : int | None, optional
        Native GLPI identifier of the referenced item.
    name : str | None, optional
        Server-provided display name.
    completename : str | None, optional
        Server-provided fully qualified name.
    """

    id: int | None = None
    name: str | None = None
    completename: str | None = None
