"""GLPI pending-reason schemas.

A ticket is paused when its status is ``4`` (Pending) and, optionally, one
``PendingReason_Item`` row links it to an entry of the ``PendingReason``
catalogue. Two read models cover the two halves:

* :class:`PendingReason` -- one catalogue entry, read from the v2
  ``/Assistance/PendingReason`` routes.
* :class:`PendingReasonItem` -- the row linking one ticket to a catalogue
  entry, read from the legacy v1 API (the v2 item schema omits the
  catalogue id).

Both are read models only: catalogue entries are configuration objects the
client does not write, and an item is written with a handful of arguments
rather than a request model.
"""

from __future__ import annotations

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema._common import IdNameRef


class PendingReason(GlpiModel):
    """One entry of the ``PendingReason`` catalogue (v2).

    The template and calendar links the server returns are not declared;
    they land in :attr:`~glpi_python_client.models._base.GlpiModel.extra_payload`.

    Parameters
    ----------
    id : int | None, optional
        Native GLPI identifier of the reason.
    name : str | None, optional
        Display name of the reason.
    entity : IdNameRef | None, optional
        Reference to the owning GLPI entity.
    is_recursive : bool | None, optional
        Whether the reason is visible to child entities.
    is_default : bool | None, optional
        Whether the reason is the default one.
    followup_frequency : int | None, optional
        Delay between automatic follow-ups, in seconds. The catalogue
        value is not copied onto a ticket's item.
    followups_before_resolution : int | None, optional
        Number of automatic follow-ups before the ticket is resolved.
    comment : str | None, optional
        Free-form comment of the reason.
    """

    id: int | None = None
    name: str | None = None
    entity: IdNameRef | None = None
    is_recursive: bool | None = None
    is_default: bool | None = None
    followup_frequency: int | None = None
    followups_before_resolution: int | None = None
    comment: str | None = None


class PendingReasonItem(GlpiModel):
    """The ``PendingReason_Item`` row of one paused ticket (v1).

    At most one row exists per ticket. GLPI removes it by itself when the
    ticket leaves status ``4`` after having been pending.

    Parameters
    ----------
    id : int | None, optional
        Native identifier of the item row.
    itemtype : str | None, optional
        Itemtype the row is attached to (``"Ticket"``).
    items_id : int | None, optional
        Identifier of the item the row is attached to.
    pendingreasons_id : int | None, optional
        Identifier of the catalogue entry. GLPI stores an id that is not
        in the catalogue without complaint.
    followup_frequency : int | None, optional
        Delay between automatic follow-ups, in seconds. ``0`` when the
        item was created without a frequency.
    followups_before_resolution : int | None, optional
        Number of automatic follow-ups before the ticket is resolved.
    bump_count : int | None, optional
        Number of automatic follow-ups already sent.
    last_bump_date : str | None, optional
        Date of the last automatic follow-up, as GLPI returns it.
    previous_status : int | None, optional
        Ticket status before the pause.
    """

    id: int | None = None
    itemtype: str | None = None
    items_id: int | None = None
    pendingreasons_id: int | None = None
    followup_frequency: int | None = None
    followups_before_resolution: int | None = None
    bump_count: int | None = None
    last_bump_date: str | None = None
    previous_status: int | None = None


__all__ = ["PendingReason", "PendingReasonItem"]
