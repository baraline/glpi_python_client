"""In-memory client factory for this tree's unit tests.

This module exists once, here, and unasync generates its twin under
``_sync/``. ``AsyncGlpiClient`` is already a substitution key, so the
generated copy returns a ``GlpiClient`` and the factory is spelled
``make_client`` on both sides -- call sites in the source and in the
generated twin read identically.

It lives beside the tree rather than in ``glpi_python_client.testing``
because that module is a published downstream helper whose factories must
keep their current names; this one has to change its return type when the
tree is transformed.
"""

from __future__ import annotations

from glpi_python_client import GlpiClient
from glpi_python_client.testing.utils import DEFAULT_CLIENT_CONFIG

__all__ = ["make_client"]


def make_client(**overrides: object) -> GlpiClient:
    """Return a test client with no real HTTP plumbing.

    Any constructor keyword can be overridden while the rest of the shared
    base configuration is reused.
    """

    config = dict(DEFAULT_CLIENT_CONFIG)
    config.update(overrides)
    return GlpiClient(**config)  # type: ignore[arg-type]
