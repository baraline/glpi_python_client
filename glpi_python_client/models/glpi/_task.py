"""Typed GLPI task model.

The task model represents parsed task timeline entries returned by GLPI.
"""

from __future__ import annotations

from datetime import datetime

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.glpi._user import GlpiUser


class GlpiTask(GlpiModel):
    """GLPI task rich object.

    Parameters
    ----------
    task_id : str | None, optional
        Native GLPI task identifier.
    ticket_id : str | None, optional
        Linked GLPI ticket identifier when the task belongs to one ticket.
    user_id : str | None, optional
        Linked GLPI user identifier.
    user : GlpiUser | None, optional
        Parsed task user when GLPI returns nested user data.
    duration : int | None, optional
        Task duration as returned by GLPI, usually through ``actiontime``.
    date : datetime | None, optional
        Primary GLPI task date when available.
    content : str | None, optional
        Task body in canonical Markdown.
    created_at : datetime | None, optional
        Creation timestamp.
    updated_at : datetime | None, optional
        Last update timestamp.
    author : GlpiUser | None, optional
        Task author.
    editor : GlpiUser | None, optional
        Last editor.
    is_private : bool, optional
        Whether the task is private.
    entity : int | dict[str, object] | None, optional
        Owning or linked GLPI entity when the API returns one.
    """

    task_id: str | None = None
    ticket_id: str | None = None
    user_id: str | None = None
    user: GlpiUser | None = None
    duration: int | None = None
    date: datetime | None = None
    content: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    author: GlpiUser | None = None
    editor: GlpiUser | None = None
    is_private: bool = False
    entity: int | dict[str, object] | None = None
