"""Synchronous GLPI v2 implementation exports.

The synchronous client is assembled from mixins grouped by endpoint area.
This package exposes the combined synchronous API mixin used by
``GlpiClient``.
"""

from __future__ import annotations

from glpi_python_client.clients.v2.sync.api import GlpiApiClientMixin

__all__ = ["GlpiApiClientMixin"]
