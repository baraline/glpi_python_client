"""Enumerations advertised by the GLPI OpenAPI contract.

These enums hold the integer identifiers that the contract documents on
relevant fields (ticket status, urgency/impact/priority, request type, task
state, solution status, timeline position, and so on). They stay numeric so
they can be dropped directly into request bodies and RSQL filters.
"""

from __future__ import annotations

from enum import IntEnum


class GlpiEnum(IntEnum):
    """Base enum exposing small GLPI convenience helpers.

    The enums remain numeric so they can be passed directly to filters and
    request parameters, while the helper methods keep RSQL string generation
    on the public surface.
    """

    @property
    def glpi_id(self) -> int:
        """Return the numeric GLPI identifier represented by this enum.

        Returns
        -------
        int
            Numeric GLPI identifier.
        """

        return int(self)

    def rsql_equals(self, field: str) -> str:
        """Return one equality RSQL fragment for this enum value.

        Parameters
        ----------
        field : str
            GLPI field name used in the filter.

        Returns
        -------
        str
            RSQL equality expression of the form ``"<field>==<value>"``.
        """

        return f"{field}=={int(self)}"


class GlpiTicketStatus(GlpiEnum):
    """GLPI ticket status identifiers as advertised by the contract.

    The contract enum on ``Ticket.status.id`` is ``[1, 10, 2, 3, 4, 5, 6]``
    where ``10`` represents the validation step that sits between ``NEW`` and
    ``ASSIGNED``.
    """

    NEW = 1
    VALIDATION = 10
    ASSIGNED = 2
    PLANNED = 3
    PENDING = 4
    SOLVED = 5
    CLOSED = 6


class GlpiPriority(GlpiEnum):
    """Common GLPI urgency, impact, and priority identifiers.

    The contract advertises the same ``[1, 2, 3, 4, 5]`` enum on the
    ``urgency``, ``impact``, and ``priority`` ticket fields, but the live
    server does not honour that for ``priority``: GLPI's priority scale has
    a sixth level, ``Major``, which it derives from urgency and impact.
    ``urgency`` and ``impact`` really do stop at 5.

    :attr:`MAJOR` is therefore included even though the contract omits it,
    following the same rule the timeline helpers use -- observed server
    behaviour wins over the published contract. Leaving it out was not a
    cosmetic gap: ``priority`` is typed with this enum on ``GetTicket``, so
    a single ``Major`` ticket anywhere in a result set failed validation and
    took the whole search down with it, which is exactly the kind of ticket
    a reporting query is most likely to touch.

    The cost of sharing one enum across the three fields is that ``urgency``
    and ``impact`` now also accept 6, which GLPI will never send. Accepting
    a value that cannot occur is harmless; rejecting one that does occur was
    not.
    """

    VERY_LOW = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    VERY_HIGH = 5
    MAJOR = 6


class GlpiTicketType(GlpiEnum):
    """GLPI ticket ``type`` identifiers as advertised by the contract."""

    INCIDENT = 1
    REQUEST = 2


class GlpiGlobalValidation(GlpiEnum):
    """GLPI ``Ticket.global_validation`` enum values."""

    NONE = 1
    WAITING = 2
    ACCEPTED = 3
    REFUSED = 4


class GlpiSolutionStatus(GlpiEnum):
    """GLPI ``Solution.status`` enum values."""

    NONE = 1
    WAITING = 2
    ACCEPTED = 3
    REFUSED = 4


class GlpiTaskState(GlpiEnum):
    """GLPI ``TicketTask.state`` enum values."""

    INFORMATION = 0
    TODO = 1
    DONE = 2


class GlpiTimelinePosition(GlpiEnum):
    """Timeline position values shared by Followup, Solution and TicketTask.

    The contract advertises ``[-1, 0, 1, 2, 3, 4]`` on
    ``timeline_position``. ``LEFT`` and ``RIGHT`` follow the GLPI UI
    conventions.
    """

    INVALID = -1
    NONE = 0
    LEFT = 1
    RIGHT = 2
    LEFT_BIG = 3
    RIGHT_BIG = 4


class GlpiUserAuthType(GlpiEnum):
    """GLPI ``User.authtype`` enum values.

    The contract advertises ``[1, 2, 3, 4, 5, 6]`` without textual labels.
    Names map to the GLPI source enum order.
    """

    LOCAL = 1
    LDAP = 2
    MAIL = 3
    CAS = 4
    X509 = 5
    EXTERNAL = 6


__all__ = [
    "GlpiEnum",
    "GlpiGlobalValidation",
    "GlpiPriority",
    "GlpiSolutionStatus",
    "GlpiTaskState",
    "GlpiTicketStatus",
    "GlpiTicketType",
    "GlpiTimelinePosition",
    "GlpiUserAuthType",
]
