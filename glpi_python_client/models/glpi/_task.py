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
    content : str | None, optional
        Task body in canonical Markdown.
    task_id : str | None, optional
        Native GLPI task identifier.
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
    """

    task_id: str | None = None
    content: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    author: GlpiUser | None = None
    editor: GlpiUser | None = None
    is_private: bool = False
