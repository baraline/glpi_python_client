"""Reusable client-layer building blocks shared across the API mixins.

The commons package centralises constants, HTTP helpers, RSQL filter
builders, transport, and the client configuration helpers
used by the per-endpoint mixins under :mod:`glpi_python_client._async.clients.api`
and the higher-level helpers under :mod:`glpi_python_client._async.clients.custom`.
"""

from __future__ import annotations
