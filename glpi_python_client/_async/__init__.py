"""Hand-written client tree.

This package is the single source of truth for client code. Its sibling
``glpi_python_client._sync`` is generated from it by ``unasync_build.py``
and checked in; CI regenerates and diffs to keep the two from drifting.

Prose written here is copied verbatim into the generated tree -- the
codegen rewrites tokens, not sentences. Docstrings under this package are
therefore worded so they read correctly on both surfaces: describe *what* a
helper does, and leave whether it blocks or awaits to the signature.
"""

from __future__ import annotations

__all__: list[str] = []
