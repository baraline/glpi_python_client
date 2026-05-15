"""Shared testing exports for the GLPI client package.

This package gathers reusable fake responses, record builders, and client
factories so unit tests can share realistic test data without repeating setup.
"""

from __future__ import annotations

from glpi_python_client.testing.utils import (
    FakeResponse,
    SearchResponse,
    TicketResponse,
    TokenResponse,
    make_client,
)

__all__ = [
    "FakeResponse",
    "SearchResponse",
    "TicketResponse",
    "TokenResponse",
    "make_client",
]
