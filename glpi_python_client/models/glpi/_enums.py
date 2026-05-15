"""Public GLPI enum values.

These enums expose the numeric identifiers commonly used by the GLPI ticket
API while keeping package-root imports stable for callers.
"""

from __future__ import annotations

from enum import IntEnum


class GlpiEnum(IntEnum):
    """Base enum exposing small GLPI convenience helpers.

    The enums remain numeric so they can be passed directly to filters and
    request parameters, while the helper methods keep RSQL string generation on
    the public surface.
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
            RSQL equality expression.
        """

        return f"{field}=={int(self)}"


class GlpiTicketStatus(GlpiEnum):
    """Common GLPI ticket status identifiers."""

    NEW = 1
    ASSIGNED = 2
    PLANNED = 3
    PENDING = 4
    SOLVED = 5
    CLOSED = 6


class GlpiPriority(GlpiEnum):
    """Common GLPI priority identifiers."""

    VERY_LOW = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    VERY_HIGH = 5


class GlpiTicketType(GlpiEnum):
    """Common GLPI ticket type identifiers."""

    INCIDENT = 1
    REQUEST = 2


__all__ = [
    "GlpiEnum",
    "GlpiPriority",
    "GlpiTicketStatus",
    "GlpiTicketType",
]
