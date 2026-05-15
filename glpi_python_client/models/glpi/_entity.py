"""Typed GLPI entity model.

The entity model is used for parsed directory-style entity search responses and
keeps the public field names stable even when GLPI varies the raw payload keys.
"""

from __future__ import annotations

from glpi_python_client.models._base import GlpiModel


class GlpiEntity(GlpiModel):
    """GLPI entity rich object.

    Parameters
    ----------
    entity_id : str | None, optional
        Native GLPI entity identifier.
    name : str | None, optional
        Entity short display name.
    complete_name : str | None, optional
        Fully qualified entity name when GLPI exposes one.
    comment : str | None, optional
        Optional descriptive comment.
    """

    entity_id: str | None = None
    name: str | None = None
    complete_name: str | None = None
    comment: str | None = None
