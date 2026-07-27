"""Client class for one GLPI surface.

The concrete client composes every per-endpoint mixin from
:mod:`glpi_python_client._sync.clients.api`, the aggregated helpers from
:mod:`glpi_python_client._sync.clients.custom`, and the transport mixin
from :mod:`glpi_python_client._sync.clients.commons`.

Only one of the two client trees is written by hand; the other is
generated from it. Both expose the same endpoint surface, so the choice
between them is purely about the caller's runtime model.
"""

from __future__ import annotations

from glpi_python_client._sync.clients.client import GlpiClient

__all__ = ["GlpiClient"]
