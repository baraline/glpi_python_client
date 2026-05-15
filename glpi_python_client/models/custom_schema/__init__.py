"""Custom aggregated views that have no native GLPI endpoint.

The :mod:`custom_schema` package gathers Pydantic models that compose
several GLPI API objects into one richer view used by the package's
high-level workflows. These models are produced by the client side and are
not part of the GLPI OpenAPI contract.
"""

from glpi_python_client.models.custom_schema._ticket_context import (
    GlpiTicketContext,
)

__all__ = ["GlpiTicketContext"]
